#pragma once
#include <ArduinoJson.h>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace meeting {
constexpr size_t kMaxText = 38;
constexpr size_t kMaxLine = 383;
enum class Status { Ok, Empty, Unavailable };
enum class Update { Rejected, Unchanged, Changed };

// Fixed storage and newline recovery keep a malformed or incomplete USB command
// from consuming memory or joining the next command to an oversized one.
class LineBuffer {
public:
    const char* push(char ch) {
        if (ch == '\n') {
            const bool complete = !discard_ && used_ > 0;
            if (used_ && bytes_[used_-1] == '\r') --used_;
            bytes_[used_] = '\0';
            used_ = 0;
            discard_ = false;
            return complete ? bytes_ : nullptr;
        }
        if (discard_) return nullptr;
        if (ch == '\0' || used_ == kMaxLine) {
            discard_ = true;
            return nullptr;
        }
        bytes_[used_++] = ch;
        return nullptr;
    }
private:
    char bytes_[kMaxLine+1] = {};
    size_t used_ = 0;
    bool discard_ = false;
};

} // namespace meeting
