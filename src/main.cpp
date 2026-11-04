#include "fastwy.hpp"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <locale>
#include <set>
#include <stdexcept>
#include <utility>

namespace {

std::vector<std::string> split(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (true) {
        const auto comma = line.find(',', start);
        fields.push_back(line.substr(start, comma - start));
        if (comma == std::string::npos) {
            return fields;
        }
        start = comma + 1;
    }
}

void read_csv_rows(const std::string& path,
                   const std::function<void(std::vector<std::string>)>& consume) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open " + path);
    }
    bool first = true;
    std::string line;
    while (std::getline(input, line)) {
        if (first && line.compare(0, 3, "\xef\xbb\xbf") == 0) {
            line.erase(0, 3);
        }
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.empty() || line.find_first_of("\"\t") != std::string::npos) {
            throw std::runtime_error(path + ": expected nonempty, unquoted CSV rows");
        }
        consume(split(line));
        first = false;
    }
    if (!input.eof() || first) {
        throw std::runtime_error(path + ": cannot read CSV rows");
    }
}

std::vector<std::vector<std::string>> read_csv(const std::string& path) {
    std::vector<std::vector<std::string>> rows;
    read_csv_rows(path, [&](std::vector<std::string> row) {
        rows.push_back(std::move(row));
    });
    return rows;
}

void set_binary(Bits& bits, std::size_t index, const std::string& value) {
    if (value == "1") {
        bits[index / 64] |= std::uint64_t{1} << (index % 64);
    } else if (value != "0") {
        throw std::runtime_error("expected a binary value (0 or 1)");
    }
}

Dataset read_data(const std::string& item_path, const std::string& label_path) {
    const auto items = read_csv(item_path);
    const auto labels = read_csv(label_path);
    if (items.size() != labels.size() || items.size() < 3 ||
        items.front().size() < 2 || labels.front().size() != 2) {
        throw std::runtime_error("expected matching CSV tables with headers, objects and features");
    }
    Dataset data;
    data.size = items.size() - 1;
    data.names.assign(items.front().begin() + 1, items.front().end());
    data.labels.resize((data.size + 63) / 64);
    data.features.assign(data.names.size(), Bits(data.labels.size()));
    std::set<std::string> names(data.names.begin(), data.names.end());
    if (names.count("") || names.size() != data.names.size()) {
        throw std::runtime_error("feature names must be nonempty and unique");
    }
    std::set<std::string> ids;
    std::size_t positives = 0;
    for (std::size_t row = 1; row < items.size(); ++row) {
        if (items[row].size() != data.names.size() + 1 || labels[row].size() != 2) {
            throw std::runtime_error("incorrect column count on row " + std::to_string(row + 1));
        }
        const auto& id = items[row][0];
        if (id.empty() || id != labels[row][0] || !ids.insert(id).second) {
            throw std::runtime_error("object IDs must be unique and in the same order in both files");
        }
        set_binary(data.labels, row - 1, labels[row][1]);
        positives += labels[row][1] == "1";
        for (std::size_t j = 0; j < data.names.size(); ++j) {
            set_binary(data.features[j], row - 1, items[row][j + 1]);
        }
    }
    if (positives == 0 || positives == data.size) {
        throw std::runtime_error("both classes must be present");
    }
    return data;
}

std::vector<Bits> read_permutations(const Dataset& data, const std::string& path) {
    std::size_t expected = 0;
    for (std::size_t i = 0; i < data.size; ++i) {
        expected += (data.labels[i / 64] >> (i % 64)) & 1;
    }
    std::vector<Bits> permutations;
    read_csv_rows(path, [&](const std::vector<std::string>& row) {
        if (permutations.size() == 10000) {
            throw std::runtime_error("permutation file must contain at most 10000 rows");
        }
        if (row.size() != data.size) {
            throw std::runtime_error("permutation row must contain one label per object");
        }
        Bits labels(data.labels.size());
        std::size_t positives = 0;
        for (std::size_t i = 0; i < row.size(); ++i) {
            set_binary(labels, i, row[i]);
            positives += row[i] == "1";
        }
        if (positives != expected) {
            throw std::runtime_error("permutation must preserve the number of positive labels");
        }
        permutations.push_back(std::move(labels));
    });
    return permutations;
}

std::uint32_t unsigned_number(const std::string& value) {
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos) {
        throw std::runtime_error("expected a nonnegative integer");
    }
    const auto number = std::stoull(value);
    if (number > std::numeric_limits<std::uint32_t>::max()) {
        throw std::runtime_error("integer is out of range");
    }
    return static_cast<std::uint32_t>(number);
}

void print_p(long double log_p) {
    if (!std::isfinite(log_p)) {
        std::cout << '0';
        return;
    }
    // Keep probabilities representable in text even below the floating-point range.
    const auto exponent = static_cast<long long>(std::floor(log_p / std::log(10.0L)));
    const auto mantissa = std::exp(log_p - exponent * std::log(10.0L));
    std::cout << std::setprecision(12) << mantissa << 'e' << exponent;
}

void write_result(const Dataset& data, const Result& result) {
    std::cout << "# alpha=0.05\n# permutations=" << result.permutations << "\n# threshold=";
    print_p(result.log_threshold);
    std::cout << "\n# significant_patterns=" << result.findings.size()
              << "\npattern\tsupport\tpositives\tp_raw\tp_adjusted\tadjusted_count\n";
    for (const auto& finding : result.findings) {
        for (std::size_t i = 0; i < finding.items.size(); ++i) {
            if (i != 0) {
                std::cout << ',';
            }
            std::cout << data.names[finding.items[i]];
        }
        std::cout << '\t' << finding.support << '\t' << finding.positives << '\t';
        print_p(finding.log_p);
        std::cout << '\t' << static_cast<long double>(finding.adjusted_count) / result.permutations
                  << '\t' << finding.adjusted_count << '\n';
    }
}

} // namespace

int main(int argc, char** argv) {
    std::cout.imbue(std::locale::classic());
    try {
        const bool exact = argc == 4 && std::string(argv[3]) == "--exact";
        const bool from_file = argc == 5 && std::string(argv[3]) == "--permutation-file";
        if (!exact && argc != 5) {
            std::cerr << "Usage: fastwy items.csv labels.csv "
                         "{permutations seed | --exact | --permutation-file path}\n";
            return 2;
        }
        const auto data = read_data(argv[1], argv[2]);
        std::vector<Bits> permutations;
        if (exact) {
            permutations = exact_labels(data);
        } else if (from_file) {
            permutations = read_permutations(data, argv[4]);
        } else {
            const auto count = unsigned_number(argv[3]);
            if (count == 0 || count > 10000) {
                throw std::runtime_error("permutation count must be in 1..10000");
            }
            permutations = random_labels(data, count, unsigned_number(argv[4]));
        }
        const ClosedMiner miner(data);
        write_result(data, fastwy(data, miner, permutations));
    } catch (const std::exception& error) {
        std::cerr << "fastwy: " << error.what() << '\n';
        return 1;
    }
}
