// Include the implementation to exercise its internal Fisher kernel directly.
#include "../src/fastwy.cpp"

#include <cmath>
#include <iostream>
#include <map>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

int main() {
    try {
        Fisher fisher(15, 7);
        const auto& tail = fisher.tail(5);
        require(std::fabs(std::exp(tail[5 - fisher.lower(5)]) - 45.0L / 6435) < 1e-14L,
                "Fisher right tail differs from exact fraction");
        for (std::size_t s = 1; s < 7; ++s) {
            require(fisher.best(s + 1) < fisher.best(s), "Tarone bound is not monotone");
        }
        Fisher large(8124, 3916);
        require(std::isfinite(large.tail(3916).back()) && large.tail(3916).back() < -1000,
                "Fisher logarithm lost an extremely small probability");

        Dataset data{4, {"A", "A_copy", "constant", "B"},
                     {{3}, {3}, {15}, {6}}, {3}};
        ClosedMiner miner(data);
        const std::map<std::uint64_t, std::vector<std::size_t>> expected{
            {3, {0, 1, 2}}, {15, {2}}, {6, {2, 3}}, {2, {0, 1, 2, 3}}
        };
        std::map<std::uint64_t, std::vector<std::size_t>> actual;
        miner.enumerate(1, 4, [&](const Pattern& pattern) {
            require(actual.emplace(pattern.coverage[0], pattern.items).second,
                    "Miner emitted duplicate coverage");
        });
        require(actual == expected, "Miner missed or incorrectly closed a coverage");
        miner.enumerate(2, 2, [&](const Pattern& pattern) {
            require(pattern.support == 2, "Miner violated support interval");
        });
        const auto permutations = exact_labels(data);
        require(permutations.size() == 6, "Wrong number of exact labelings");
        for (const auto& labels : permutations) {
            require(overlap(labels, labels) == 2, "Permutation changed positive count");
        }
        const auto result = fastwy(data, miner, std::vector<Bits>(20, data.labels));
        require(!std::isfinite(result.log_threshold) && result.findings.empty(),
                "A complete minimum tie should produce no admissible threshold");
        std::cout << "PASS: Fisher, extreme probabilities, closed miner, permutations, threshold ties\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
