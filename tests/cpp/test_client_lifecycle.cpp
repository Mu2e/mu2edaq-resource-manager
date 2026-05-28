// Smoke test for ResourceManagerClient libcurl lifecycle (issue #4).
//
// Verifies that constructing and destroying clients does not tear down
// libcurl's process-wide global state for other live clients. Under the old
// per-instance curl_global_cleanup() this pattern could crash or leave libcurl
// deinitialized. No server is required: a connection error from the surviving
// client is acceptable; the point is that libcurl keeps functioning.

#include "ResourceManagerClient.h"

#include <iostream>

using namespace mu2e;

int main()
{
    try {
        ResourceManagerClient survivor("localhost", 8080);

        {
            ResourceManagerClient temporary("localhost", 8081);
            (void)temporary;
        }  // destroying `temporary` must not affect `survivor`'s libcurl

        // Many client lifetimes in one process must not deinitialize libcurl.
        for (int i = 0; i < 1000; ++i) {
            ResourceManagerClient c("localhost", 8080);
            (void)c;
        }

        // Continue using the surviving client. A connection error is expected
        // when no server is listening; a crash would indicate torn-down state.
        try {
            survivor.getStatus();
        } catch (const ResourceManagerException&) {
            // expected without a running server
        }
    } catch (const std::exception& e) {
        std::cerr << "FAIL: unexpected exception: " << e.what() << "\n";
        return 1;
    }

    std::cout << "PASS: client lifecycle is process-safe\n";
    return 0;
}
