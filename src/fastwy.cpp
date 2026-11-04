#include "fastwy.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <map>
#include <numeric>
#include <random>
#include <stdexcept>
#include <utility>

namespace {

constexpr long double no_p = -std::numeric_limits<long double>::infinity();

std::size_t popcount(std::uint64_t word) {
#if defined(__GNUC__) || defined(__clang__)
    return static_cast<std::size_t>(__builtin_popcountll(word));
#else
    std::size_t count = 0;
    for (; word != 0; word &= word - 1) {
        ++count;
    }
    return count;
#endif
}

std::size_t overlap(const Bits& first, const Bits& second) {
    std::size_t count = 0;
    for (std::size_t i = 0; i < first.size(); ++i) {
        count += popcount(first[i] & second[i]);
    }
    return count;
}

Bits intersect(const Bits& first, const Bits& second) {
    Bits result(first.size());
    for (std::size_t i = 0; i < first.size(); ++i) {
        result[i] = first[i] & second[i];
    }
    return result;
}

bool contains(const Bits& feature, const Bits& coverage) {
    for (std::size_t i = 0; i < coverage.size(); ++i) {
        if ((coverage[i] & feature[i]) != coverage[i]) {
            return false;
        }
    }
    return true;
}

void close_pattern(const Dataset& data, Pattern& pattern) {
    for (std::size_t i = 0; i < data.features.size(); ++i) {
        if (contains(data.features[i], pattern.coverage)) {
            pattern.items.push_back(i);
        }
    }
}

void visit_closed(const Dataset& data, const Pattern& parent, std::size_t start,
                  std::size_t minimum, std::size_t maximum, const PatternVisitor& visit) {
    if (!parent.items.empty() && parent.support <= maximum) {
        visit(parent);
    }
    for (std::size_t item = start; item < data.features.size(); ++item) {
        if (std::binary_search(parent.items.begin(), parent.items.end(), item)) {
            continue;
        }
        auto coverage = intersect(parent.coverage, data.features[item]);
        const auto support = overlap(coverage, coverage);
        if (support < minimum) {
            continue;
        }
        Pattern child{{}, std::move(coverage), support};
        close_pattern(data, child);
        // A closure adding an earlier item belongs to an earlier branch.
        if (!std::equal(parent.items.begin(),
                        std::lower_bound(parent.items.begin(), parent.items.end(), item),
                        child.items.begin(),
                        std::lower_bound(child.items.begin(), child.items.end(), item))) {
            continue;
        }
        visit_closed(data, child, item + 1, minimum, maximum, visit);
    }
}

long double log_add(long double first, long double second) {
    if (first == no_p) {
        return second;
    }
    return std::max(first, second) + std::log1p(std::exp(-std::abs(first - second)));
}

bool same_p(long double first, long double second) {
    const auto scale = 1 + std::max(std::abs(first), std::abs(second));
    return std::abs(first - second) <= 64 * std::numeric_limits<long double>::epsilon() * scale;
}

class Fisher {
public:
    Fisher(std::size_t size, std::size_t positives) : size_(size), positives_(positives) {}

    const std::vector<long double>& tail(std::size_t support) {
        auto position = tails_.find(support);
        if (position == tails_.end()) {
            position = tails_.emplace(support, make_tail(support)).first;
        }
        return position->second;
    }

    long double p(std::size_t support, std::size_t positives) {
        return tail(support)[positives - lower(support)];
    }

    long double best(std::size_t support) {
        return p(support, std::min(support, positives_));
    }

    std::size_t lower(std::size_t support) const {
        const auto negatives = size_ - positives_;
        return support > negatives ? support - negatives : 0;
    }

private:
    std::vector<long double> make_tail(std::size_t support) const {
        const auto lo = lower(support);
        const auto hi = std::min(support, positives_);
        const auto negatives = size_ - positives_;
        std::vector<long double> tail(hi - lo + 1);
        long double mass = 0;
        long double cumulative = 0;
        // Walk the hypergeometric masses backwards, then normalize in log space.
        for (auto a = hi; a > lo; --a) {
            mass += std::log(static_cast<long double>(a))
                + std::log(static_cast<long double>(negatives - (support - a)))
                - std::log(static_cast<long double>(positives_ - a + 1))
                - std::log(static_cast<long double>(support - a + 1));
            cumulative = log_add(cumulative, mass);
            tail[a - lo - 1] = cumulative;
        }
        for (auto& value : tail) {
            value -= cumulative;
        }
        return tail;
    }

    std::size_t size_;
    std::size_t positives_;
    std::map<std::size_t, std::vector<long double>> tails_;
};

Bits pack_labels(const std::vector<unsigned char>& values) {
    Bits result((values.size() + 63) / 64);
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (values[i]) {
            result[i / 64] |= std::uint64_t{1} << (i % 64);
        }
    }
    return result;
}

} // namespace

void ClosedMiner::enumerate(std::size_t minimum, std::size_t maximum,
                            const PatternVisitor& visit) const {
    Pattern root{{}, Bits(data_.labels.size(), ~std::uint64_t{0}), data_.size};
    if (data_.size % 64) {
        root.coverage.back() = (std::uint64_t{1} << (data_.size % 64)) - 1;
    }
    close_pattern(data_, root);
    visit_closed(data_, root, 0, minimum, maximum, visit);
}

std::vector<Bits> random_labels(const Dataset& data, std::size_t count, std::uint32_t seed) {
    std::vector<unsigned char> labels(data.size);
    std::fill_n(labels.begin(), overlap(data.labels, data.labels), 1);
    std::mt19937 random(seed);
    std::vector<Bits> permutations;
    permutations.reserve(count);
    for (std::size_t i = 0; i < count; ++i) {
        std::shuffle(labels.begin(), labels.end(), random);
        permutations.push_back(pack_labels(labels));
    }
    return permutations;
}

std::vector<Bits> exact_labels(const Dataset& data) {
    if (data.size > 20) {
        throw std::runtime_error("--exact supports at most 20 objects");
    }
    std::vector<unsigned char> labels(data.size);
    const auto positives = overlap(data.labels, data.labels);
    std::fill(labels.end() - positives, labels.end(), 1);
    std::vector<Bits> permutations;
    do {
        permutations.push_back(pack_labels(labels));
    } while (std::next_permutation(labels.begin(), labels.end()));
    return permutations;
}

Result fastwy(const Dataset& data, const Miner& miner, const std::vector<Bits>& permutations) {
    const auto positives = overlap(data.labels, data.labels);
    Fisher fisher(data.size, positives);
    std::vector<long double> minima(permutations.size(), 0);
    std::vector<std::size_t> active(permutations.size());
    std::iota(active.begin(), active.end(), 0);
    std::size_t maximum = data.size;
    std::size_t minimum = positives;

    std::vector<std::size_t> occupied;
    occupied.reserve(data.labels.size());
    while (!active.empty()) {
        miner.enumerate(minimum, maximum, [&](const Pattern& pattern) {
            const auto& tail = fisher.tail(pattern.support);
            const auto lo = fisher.lower(pattern.support);
            // Reuse the occupied words across all permutations of a sparse coverage.
            occupied.clear();
            for (std::size_t word = 0; word < pattern.coverage.size(); ++word) {
                if (pattern.coverage[word] != 0) {
                    occupied.push_back(word);
                }
            }
            for (const auto i : active) {
                if (minima[i] <= tail.back()) {
                    continue;
                }
                std::size_t a = 0;
                for (const auto word : occupied) {
                    a += popcount(pattern.coverage[word] & permutations[i][word]);
                }
                minima[i] = std::min(minima[i], tail[a - lo]);
            }
        });
        if (minimum == 1) {
            break;
        }
        maximum = minimum - 1;
        // Below the positive-class count the attainable p-value decreases
        // with support, so this bound covers the entire unvisited range.
        const auto bound = fisher.best(maximum);
        active.erase(std::remove_if(active.begin(), active.end(), [&](std::size_t i) {
            return minima[i] <= bound;
        }), active.end());
        // Use wide bands at high supports to avoid repeating miner traversal.
        minimum = maximum - maximum / 5;
    }

    std::sort(minima.begin(), minima.end());
    // At alpha = 0.05, at most floor(B/20) minima may be at or below the threshold.
    const auto budget = minima.size() / 20;
    auto cutoff = minima.begin() + budget;
    // Equivalent probabilities at different supports can round differently.
    while (cutoff != minima.begin() && same_p(*(cutoff - 1), minima[budget])) {
        --cutoff;
    }
    const auto threshold = cutoff == minima.begin() ? no_p : *(cutoff - 1);
    Result result{minima.size(), threshold, {}};

    if (threshold != no_p) {
        std::size_t minimum_testable = 1;
        while (minimum_testable <= positives && fisher.best(minimum_testable) > threshold
               && !same_p(fisher.best(minimum_testable), threshold)) {
            ++minimum_testable;
        }
        miner.enumerate(minimum_testable, data.size, [&](const Pattern& pattern) {
            const auto a = overlap(pattern.coverage, data.labels);
            const auto p = fisher.p(pattern.support, a);
            if (p <= threshold || same_p(p, threshold)) {
                auto upper = std::upper_bound(minima.begin(), minima.end(), p);
                while (upper != minima.end() && same_p(*upper, p)) {
                    ++upper;
                }
                const auto count = static_cast<std::size_t>(upper - minima.begin());
                if (count <= budget) {
                    result.findings.push_back({pattern.items, pattern.support, a, p, count});
                }
            }
        });
    }
    std::sort(result.findings.begin(), result.findings.end(), [](const Finding& a, const Finding& b) {
        return a.log_p == b.log_p ? a.items < b.items : a.log_p < b.log_p;
    });
    return result;
}
