#pragma once
#include <cstdint>

namespace live_poll {
constexpr uint32_t kFirstRetryMs = 30000;
constexpr uint32_t kMaximumRetryMs = 300000;

// Keep one schedule per project; only a completed request advances its backoff.
class Schedule {
public:
    void start(uint32_t now, uint32_t initialDelayMs) {
        completedAt_ = now;
        delayMs_ = initialDelayMs;
        retryMs_ = 0;
    }
    bool due(uint32_t now) const { return now-completedAt_ >= delayMs_; }
    uint32_t complete(uint32_t now, bool success, uint32_t normalIntervalMs,
                      uint32_t providerDelayMs = 0) {
        completedAt_ = now;
        if (success) {
            retryMs_ = 0;
            delayMs_ = normalIntervalMs;
        } else {
            retryMs_ = retryMs_ ? retryMs_*2 : kFirstRetryMs;
            if (retryMs_ > kMaximumRetryMs) retryMs_ = kMaximumRetryMs;
            // A provider's Retry-After can legitimately exceed our five-minute cap.
            delayMs_ = providerDelayMs > retryMs_ ? providerDelayMs : retryMs_;
        }
        return delayMs_;
    }
private:
    uint32_t completedAt_ = 0;
    uint32_t delayMs_ = 0;
    uint32_t retryMs_ = 0;
};
}
