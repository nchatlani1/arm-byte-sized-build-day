#pragma once
#include <cstdint>
namespace carousel {
constexpr uint32_t kSettleMs = 180;
constexpr uint32_t kManualRefreshMs = 1000;

// Direction switches are active-low buttons, not a quadrature encoder.
// One event per press; require BOTH switches released before another event.
constexpr uint32_t kPressStableMs = 25;
constexpr uint32_t kReleaseStableMs = 120;
class WheelInput {
public:
    int sample(bool up, bool down, uint32_t now) {
        const int raw = up && down ? 2 : up ? 1 : down ? -1 : 0;
        if (!initialized_ || raw != raw_) {
            initialized_ = true;
            raw_ = raw;
            changedAt_ = now;
        }
        if (raw == 0) {
            if (now-changedAt_ >= kReleaseStableMs) armed_ = true;
            return 0;
        }
        // Conflicting contacts consume the gesture, rather than choosing a direction.
        if (raw == 2) { armed_ = false; return 0; }
        if (!armed_ || now-changedAt_ < kPressStableMs) return 0;
        armed_ = false;
        return raw;
    }
private:
    bool initialized_ = false;
    bool armed_ = false; // Ignore a held switch at boot until it is released.
    int raw_ = 0;
    uint32_t changedAt_ = 0;
};
inline uint8_t step(uint8_t current, int delta, uint8_t count) {
    if (count == 0) return 0;
    const int wrapped = (static_cast<int>(current) + delta % count) % count;
    return static_cast<uint8_t>(wrapped < 0 ? wrapped + count : wrapped);
}
inline bool ready(uint32_t now, uint32_t lastInput, uint32_t lastRefresh) {
    return now-lastInput >= kSettleMs && now-lastRefresh >= kManualRefreshMs;
}
}
