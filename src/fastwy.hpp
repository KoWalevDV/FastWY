#ifndef FASTWY_HPP
#define FASTWY_HPP

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

using Bits = std::vector<std::uint64_t>;

struct Dataset {
    std::size_t size;
    std::vector<std::string> names;
    std::vector<Bits> features;
    Bits labels;
};

struct Pattern {
    std::vector<std::size_t> items;
    Bits coverage;
    std::size_t support;
};

using PatternVisitor = std::function<void(const Pattern&)>;

class Miner {
public:
    virtual ~Miner() = default;
    // Visit closed patterns whose support is within [minimum, maximum].
    virtual void enumerate(std::size_t minimum, std::size_t maximum,
                           const PatternVisitor& visit) const = 0;
};

class ClosedMiner final : public Miner {
public:
    explicit ClosedMiner(const Dataset& data) : data_(data) {}
    void enumerate(std::size_t minimum, std::size_t maximum,
                   const PatternVisitor& visit) const override;

private:
    const Dataset& data_;
};

struct Finding {
    std::vector<std::size_t> items;
    std::size_t support;
    std::size_t positives;
    long double log_p;
    std::size_t adjusted_count;
};

struct Result {
    std::size_t permutations;
    long double log_threshold;
    std::vector<Finding> findings;
};

std::vector<Bits> random_labels(const Dataset& data, std::size_t count, std::uint32_t seed);
std::vector<Bits> exact_labels(const Dataset& data);
Result fastwy(const Dataset& data, const Miner& miner, const std::vector<Bits>& permutations);

#endif
