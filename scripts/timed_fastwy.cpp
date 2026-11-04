#define main standalone_main
#include "../src/main.cpp"
#undef main

#include <chrono>

int main(int argc, char** argv) {
    using Clock = std::chrono::steady_clock;
    try {
        if (argc != 4) {
            throw std::runtime_error("usage: timed_fastwy items labels permutations");
        }
        const auto data = read_data(argv[1], argv[2]);
        const auto permutations = read_permutations(data, argv[3]);
        const auto start = Clock::now();
        const ClosedMiner miner(data);
        const auto result = fastwy(data, miner, permutations);
        const auto elapsed = std::chrono::duration<double>(Clock::now() - start).count();
        write_result(data, result);
        std::cerr << "search_seconds=" << elapsed << '\n';
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
