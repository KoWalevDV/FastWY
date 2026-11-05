#define main standalone_main
#include "../src/main.cpp"
#undef main
#include "../src/fastwy.cpp"

#include <cstdlib>

namespace {

std::vector<std::size_t> numbers(const std::string& line) {
    std::vector<std::size_t> result;
    const auto* cursor = line.c_str();
    while (*cursor != '\0') {
        if (*cursor == ' ' || *cursor == '(' || *cursor == ')' || *cursor == '\r') {
            ++cursor;
            continue;
        }
        char* next = nullptr;
        const auto number = std::strtoul(cursor, &next, 10);
        if (next == cursor) {
            throw std::runtime_error("invalid LCM output");
        }
        result.push_back(number);
        cursor = next;
    }
    return result;
}

Result from_lcm(const Dataset& data, const std::vector<Bits>& permutations,
                const std::string& path, std::size_t floor) {
    const auto positives = overlap(data.labels, data.labels);
    if (floor == 0 || floor > positives) {
        throw std::runtime_error("invalid support floor");
    }
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open LCM output");
    }
    Fisher fisher(data.size, positives);
    const auto blocks = (permutations.size() + 63) / 64;
    std::vector<std::uint64_t> membership(data.size * blocks);
    for (std::size_t i = 0; i < permutations.size(); ++i) {
        for (std::size_t row = 0; row < data.size; ++row) {
            if (permutations[i][row / 64] & (std::uint64_t{1} << (row % 64))) {
                membership[row * blocks + i / 64] |= std::uint64_t{1} << (i % 64);
            }
        }
    }
    std::vector<long double> minima(permutations.size(), 0);
    const auto budget = minima.size() / 20;
    std::vector<long double> ranked(minima.size());
    std::vector<Finding> potential;
    std::string line, cover;
    Bits coverage(data.labels.size());
    std::vector<std::size_t> occupied;
    occupied.reserve(coverage.size());
    const auto observation_cap = std::log(0.05L);
    long double rank_bound = 0;
    std::size_t records = 0;
    while (std::getline(input, line)) {
        if (!std::getline(input, cover)) {
            throw std::runtime_error("incomplete LCM record");
        }
        auto items = numbers(line);
        if (items.size() < 2) {
            continue;
        }
        ++records;
        const auto support = items.back();
        items.pop_back();
        if (support < floor || support > data.size) {
            throw std::runtime_error("invalid LCM support");
        }
        if (records % 10000 == 0) {
            // The rank can only decrease. Values above its current upper bound
            // cannot enter the final threshold or a reported adjusted count.
            ranked = minima;
            std::nth_element(ranked.begin(), ranked.begin() + budget, ranked.end());
            rank_bound = ranked[budget];
        }
        const auto& tail = fisher.tail(support);
        const auto best = tail.back();
        if (best > observation_cap && best > rank_bound) {
            continue;
        }
        const auto rows = numbers(cover);
        if (rows.size() != support) {
            throw std::runtime_error("LCM support and coverage disagree");
        }
        occupied.clear();
        for (const auto row : rows) {
            if (row >= data.size) {
                throw std::runtime_error("LCM row index is out of range");
            }
            const auto word = row / 64;
            if (!coverage[word]) {
                occupied.push_back(word);
            }
            coverage[word] |= std::uint64_t{1} << (row % 64);
        }
        const auto lo = fisher.lower(support);
        std::size_t observed = 0;
        for (const auto word : occupied) {
            observed += popcount(coverage[word] & data.labels[word]);
        }
        const auto p = tail[observed - lo];
        if (p <= observation_cap) {
            for (auto& item : items) {
                if (!item || item > data.names.size()) {
                    throw std::runtime_error("LCM item index is out of range");
                }
                --item;
            }
            std::sort(items.begin(), items.end());
            potential.push_back({std::move(items), support, observed, p, 0});
        }
        if (best <= rank_bound) {
            const auto update = [&](std::size_t i) {
                if (minima[i] <= best) {
                    return;
                }
                std::size_t a = 0;
                for (const auto word : occupied) {
                    a += popcount(coverage[word] & permutations[i][word]);
                }
                minima[i] = std::min(minima[i], tail[a - lo]);
            };
            const auto required = std::lower_bound(tail.begin(), tail.end(), rank_bound,
                                                   std::greater<long double>()) - tail.begin() + lo;
            const auto anchors = std::min<std::size_t>(8, support);
            const auto outside = support - anchors;
            if (required > outside + anchors / 2) {
                // An overlap of required objects needs at least this many
                // positives among the first anchors, even if all others match.
                const auto needed = required - outside;
                for (std::size_t block = 0; block < blocks; ++block) {
                    std::uint64_t at_least[9] = {~std::uint64_t{0}};
                    for (std::size_t j = 0; j < anchors; ++j) {
                        const auto positive = membership[rows[j] * blocks + block];
                        for (auto k = std::min(j + 1, needed); k > 0; --k) {
                            at_least[k] |= at_least[k - 1] & positive;
                        }
                    }
                    auto candidates = at_least[needed];
                    while (candidates) {
                        const auto i = block * 64 + __builtin_ctzll(candidates);
                        update(i);
                        candidates &= candidates - 1;
                    }
                }
            } else {
                for (std::size_t i = 0; i < minima.size(); ++i) {
                    update(i);
                }
            }
        }
        for (const auto word : occupied) {
            coverage[word] = 0;
        }
    }

    std::sort(minima.begin(), minima.end());
    if (minima[budget] > observation_cap ||
        (floor > 1 && (fisher.best(floor - 1) <= minima[budget]
                       || same_p(fisher.best(floor - 1), minima[budget])))) {
        throw std::runtime_error("lower support needed to certify the rank");
    }
    auto cutoff = minima.begin() + budget;
    while (cutoff != minima.begin() && same_p(*(cutoff - 1), minima[budget])) {
        --cutoff;
    }
    const auto threshold = cutoff == minima.begin() ? no_p : *(cutoff - 1);
    Result result{minima.size(), threshold, {}};
    for (auto& finding : potential) {
        const auto p = finding.log_p;
        if (threshold == no_p || (p > threshold && !same_p(p, threshold))) {
            continue;
        }
        auto upper = std::upper_bound(minima.begin(), minima.end(), p);
        while (upper != minima.end() && same_p(*upper, p)) {
            ++upper;
        }
        finding.adjusted_count = static_cast<std::size_t>(upper - minima.begin());
        if (finding.adjusted_count <= budget) {
            result.findings.push_back(std::move(finding));
        }
    }
    std::sort(result.findings.begin(), result.findings.end(), [](const Finding& a, const Finding& b) {
        return a.log_p == b.log_p ? a.items < b.items : a.log_p < b.log_p;
    });
    std::cerr << "LCM patterns: " << records << "; support floor " << floor
              << "; certified rank " << budget + 1 << "; log minP at rank: " << minima[budget]
              << "; log lower bound for omitted supports: "
              << (floor > 1 ? fisher.best(floor - 1) : 0) << '\n';
    return result;
}

} // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 7) {
            throw std::runtime_error("usage: lcm_eval items labels patterns floor {count seed | --permutation-file path}");
        }
        const auto data = read_data(argv[1], argv[2]);
        std::vector<Bits> permutations;
        if (std::string(argv[5]) == "--permutation-file") {
            permutations = read_permutations(data, argv[6]);
        } else {
            const auto count = unsigned_number(argv[5]);
            if (count < 20 || count > 10000) {
                throw std::runtime_error("expected 20..10000 permutations");
            }
            permutations = random_labels(data, count, unsigned_number(argv[6]));
        }
        if (permutations.size() < 20) {
            throw std::runtime_error("expected at least 20 fixed permutations");
        }
        write_result(data, from_lcm(data, permutations, argv[3], unsigned_number(argv[4])));
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
