#include <windows.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <map>
#include <utility>
#include <vector>

using Probability = double (__cdecl *)(const std::uint32_t*, std::uint32_t, std::uint32_t);

namespace {
struct View {
    HANDLE mapping;
    const unsigned char* bytes;
    std::uint64_t length;
};
std::map<std::uintptr_t, View> views;
std::vector<std::vector<double>> probabilities;

std::uint32_t number(const unsigned char*& position) {
    std::uint32_t value;
    std::memcpy(&value, position, sizeof(value));
    position += sizeof(value);
    return value;
}
}

extern "C" __declspec(dllexport) void __cdecl clear_cache() {
    for (const auto& entry : views) {
        UnmapViewOfFile(entry.second.bytes);
        CloseHandle(entry.second.mapping);
    }
    views.clear();
    probabilities.clear();
}

extern "C" __declspec(dllexport) int __cdecl scan(
        std::uintptr_t handle, const unsigned char* labels, std::uint32_t size,
        std::uint64_t records, Probability probability, double* minimum) {
    try {
        auto found = views.find(handle);
        if (found == views.end()) {
            LARGE_INTEGER length;
            if (!GetFileSizeEx(reinterpret_cast<HANDLE>(handle), &length)) return 1;
            const auto mapping = CreateFileMappingW(reinterpret_cast<HANDLE>(handle), nullptr,
                                                   PAGE_READONLY, 0, 0, nullptr);
            if (!mapping) return 2;
            const auto bytes = static_cast<const unsigned char*>(MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, 0));
            if (!bytes) { CloseHandle(mapping); return 3; }
            found = views.emplace(handle, View{mapping, bytes, static_cast<std::uint64_t>(length.QuadPart)}).first;
        }
        const auto& view = found->second;
        const auto* position = view.bytes;
        const auto* end = position + view.length;
        for (std::uint64_t record = 0; record < records; ++record) {
            if (end - position < 8) return 4;
            const auto items = number(position);
            const auto support = number(position);
            if (std::uint64_t(items) + support > std::uint64_t(end - position) / 4) return 5;
            position += std::size_t{4} * items;
            const auto* rows = reinterpret_cast<const std::uint32_t*>(position);
            std::uint32_t positive = 0;
            for (std::uint32_t j = 0; j < support; ++j) {
                const auto row = number(position);
                if (row >= size) return 6;
                positive += labels[row];
            }
            if (probabilities.size() <= support) probabilities.resize(support + 1);
            auto& tail = probabilities[support];
            if (tail.empty()) tail.resize(support + 1, -1.0);
            auto& cached = tail[positive];
            if (cached < 0) {
                cached = probability(rows, support, positive);
                if (std::isnan(cached)) return 7;
            }
            if (cached < *minimum) *minimum = cached;
        }
        return 0;
    } catch (...) {
        return 8;
    }
}
