#include <cassert>
#include <cstdint>
#include "carousel.h"
void testWheelInput() {
    using carousel::WheelInput;
    WheelInput input;
    assert(input.sample(false,false,0)==0);
    assert(input.sample(false,false,120)==0); // Stable neutral arms the wheel.
    assert(input.sample(true,false,200)==0);
    assert(input.sample(false,false,205)==0); // Contact bounce on initial press.
    assert(input.sample(true,false,210)==0);
    assert(input.sample(true,false,234)==0);
    assert(input.sample(true,false,235)==1);
    assert(input.sample(true,false,1000)==0); // Holding does not repeat.
    assert(input.sample(false,false,1005)==0);
    assert(input.sample(false,false,1090)==0);
    assert(input.sample(true,false,1095)==0); // A late bounce defeats the old 80 ms lockout.
    assert(input.sample(true,false,1120)==0); // Still the same gesture.
    assert(input.sample(false,true,1200)==0); // Opposite contact without neutral is not a new press.
    assert(input.sample(false,true,1225)==0);
    assert(input.sample(false,false,1300)==0);
    assert(input.sample(false,false,1420)==0);
    assert(input.sample(false,true,1500)==0);
    assert(input.sample(false,true,1525)==-1); // Proper release allows a direction change.

    WheelInput bootHeld;
    assert(bootHeld.sample(true,false,0)==0);
    assert(bootHeld.sample(true,false,5000)==0);
    assert(bootHeld.sample(false,false,5010)==0);
    assert(bootHeld.sample(false,false,5130)==0);
    assert(bootHeld.sample(true,false,5200)==0);
    assert(bootHeld.sample(true,false,5225)==1);

    WheelInput conflict;
    conflict.sample(false,false,0);conflict.sample(false,false,120);
    assert(conflict.sample(true,true,200)==0);
    assert(conflict.sample(true,false,210)==0);
    assert(conflict.sample(true,false,235)==0); // Ambiguous input needs full release.
    conflict.sample(false,false,300);conflict.sample(false,false,420);
    conflict.sample(false,true,450);
    assert(conflict.sample(false,true,475)==-1);

    WheelInput wrap;
    wrap.sample(false,false,UINT32_MAX-300);
    wrap.sample(false,false,UINT32_MAX-180);
    wrap.sample(true,false,UINT32_MAX-10);
    assert(wrap.sample(true,false,14)==1); // Debounce timing survives millis wrap.

    // The sampler runs every 5 ms even when the display/UI cannot drain events.
    WheelInput duringRefresh;
    int queued=0;
    for(uint32_t now=0;now<=2000;now+=5) {
        const bool up=(now>=200 && now<700) || (now>=1000 && now<1100);
        const bool down=now>=1400 && now<1550;
        queued+=duringRefresh.sample(up,down,now);
    }
    assert(queued==1); // Two deliberate up presses and one down, regardless of hold length.
    assert(carousel::step(0,queued,4)==1);
}

int main() {
    testWheelInput();
    for (int delta=-64; delta<=64; ++delta) assert(carousel::step(0,delta,1)==0);
    assert(carousel::step(0,1,2)==1);
    assert(carousel::step(1,1,2)==0);
    assert(carousel::step(0,-1,2)==1);
    assert(carousel::step(0,1,0)==0);
    assert(carousel::step(0,1,4)==1);
    assert(carousel::step(3,1,4)==0);
    assert(carousel::step(0,-1,4)==3);
    assert(carousel::step(2,-1,4)==1);
    assert(carousel::step(0,7,4)==3);
    assert(carousel::step(1,-7,4)==2);
    assert(carousel::step(1,4,4)==1);
    for(int start=0;start<4;++start)for(int delta=-64;delta<=64;++delta) {
        const auto next=carousel::step(start,delta,4);
        assert(next<4);
        assert(carousel::step(next,-delta,4)==start);
    }
    assert(!carousel::ready(1000,900,0)); // Wait until the wheel settles.
    assert(!carousel::ready(2000,1000,1500)); // Display has not finished cooling down.
    assert(carousel::ready(2000,1800,900));
    assert(carousel::ready(1000,UINT32_MAX-100,UINT32_MAX-100)); // millis wrap.
}
