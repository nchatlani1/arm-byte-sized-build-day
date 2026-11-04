#include <cassert>
#include <cstdint>
#include "live_poll.h"

void boundary(const live_poll::Schedule& schedule, uint32_t completedAt, uint32_t delay) {
    assert(!schedule.due(completedAt));
    assert(!schedule.due(completedAt+delay-1));
    assert(schedule.due(completedAt+delay));
}

int main() {
    constexpr uint32_t normalIntervals[] = {900000, 30000, 60000};
    live_poll::Schedule projects[3];
    for(auto& project:projects) {
        project.start(0,30000);
        boundary(project,0,30000); // Preserve the initial screen's settling time.
    }

    uint32_t now=50000; // The first request took time; wait from completion.
    constexpr uint32_t failures[] = {30000,60000,120000,240000,300000};
    for(uint32_t delay:failures) {
        assert(projects[0].complete(now,false,normalIntervals[0])==delay);
        boundary(projects[0],now,delay);
        assert(projects[1].due(30000)); // Other projects retain independent schedules.
        assert(projects[2].due(30000));
        now+=delay+10000;
    }
    for(int attempt=0;attempt<1000;++attempt) {
        assert(projects[0].complete(now,false,normalIntervals[0])==300000);
        boundary(projects[0],now,300000);
        now+=310000;
    }

    for(unsigned index=0;index<3;++index) {
        auto& project=projects[index];
        assert(project.complete(now,true,normalIntervals[index])==normalIntervals[index]);
        boundary(project,now,normalIntervals[index]);
        now+=normalIntervals[index];
        assert(project.complete(now,false,normalIntervals[index])==30000);
        boundary(project,now,30000); // Success resets the failure streak, even without a redraw.
    }

    live_poll::Schedule limited;
    limited.start(100,30000);
    assert(limited.due(30100));
    assert(limited.due(60100)); // Readiness checks / unavailable queue do not advance backoff.
    assert(limited.complete(90000,false,900000,600000)==600000);
    boundary(limited,90000,600000); // Retry-After can exceed the five-minute local cap.
    assert(limited.complete(690000,false,900000,1000)==60000);
    boundary(limited,690000,60000); // A shorter provider delay cannot bypass local backoff.
    assert(limited.complete(750000,true,900000,600000)==900000);
    boundary(limited,750000,900000);

    live_poll::Schedule wrap;
    const uint32_t beforeWrap=UINT32_MAX-10000;
    wrap.start(beforeWrap,30000);
    boundary(wrap,beforeWrap,30000);
    assert(wrap.complete(beforeWrap,false,900000)==30000);
    boundary(wrap,beforeWrap,30000);
    assert(wrap.complete(beforeWrap,true,900000)==900000);
    boundary(wrap,beforeWrap,900000);
    assert(wrap.complete(beforeWrap,false,900000,600000)==600000);
    boundary(wrap,beforeWrap,600000);
}
