// relay_link.h — the dial-out relay link for Companion ESP32 sketches.
//
// This used to hold the implementation, and the CompanionRelay library was a
// COPY of it. Two copies of one protocol is precisely how a contract drifts, so
// the library is now the single source of truth and this file just forwards to
// it. The two first-party sketches keep including this path; nothing else
// changes.
//
// Usage (unchanged):
//   #include "../shared/relay_link.h"
//   static const RelayLinkConfig relayCfg = {...};
//   setup():  relayBegin(relayCfg);
//   loop():   relayLinkLoop();

#pragma once
#include "../libraries/CompanionRelay/src/CompanionRelay.h"
