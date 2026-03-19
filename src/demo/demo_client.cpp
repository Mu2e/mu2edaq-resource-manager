#include "ResourceManagerClient.h"

#include <algorithm>
#include <iostream>
#include <string>
#include <vector>

using namespace mu2e;

static const char* GREEN  = "\033[32m";
static const char* RED    = "\033[31m";
static const char* YELLOW = "\033[33m";
static const char* BOLD   = "\033[1m";
static const char* RESET  = "\033[0m";
static const char* DIM    = "\033[2m";

static void section(int n, const std::string& title)
{
    std::cout << '\n'
              << BOLD << std::string(60, '-') << RESET << '\n'
              << BOLD << " Step " << n << ": " << title << RESET << '\n'
              << BOLD << std::string(60, '-') << RESET << '\n';
}

static void printResource(const Resource& r)
{
    std::string ports;
    for (size_t i = 0; i < r.location.ports.size(); ++i) {
        if (i) ports += ',';
        ports += std::to_string(r.location.ports[i]);
    }
    const char* sc = (r.status == "available") ? GREEN : RED;
    std::cout << "  " << r.resource_class << ':' << r.name << ':' << r.enumerator
              << "  @  " << r.location.node << "  [" << ports << "]"
              << "  →  " << sc << r.status << RESET;
    if (!r.owner.empty())
        std::cout << DIM << "  (owned by " << YELLOW << r.owner << RESET << DIM << ")" << RESET;
    std::cout << '\n';
}

int main(int argc, char* argv[])
{
    std::string host = "localhost";
    int         port = 8080;
    if (argc > 1) host = argv[1];
    if (argc > 2) port = std::stoi(argv[2]);

    const std::string CLIENT_ID = "cpp-demo-client";

    std::cout << '\n'
              << BOLD << "Mu2e DAQ Resource Manager — C++ Demo Client" << RESET << '\n'
              << "Server:    " << host << ':' << port << '\n'
              << "Client ID: " << CLIENT_ID << '\n';

    ResourceManagerClient client(host, port);

    // ── 1. Server status ──────────────────────────────────────────────────
    section(1, "Server Status");
    try {
        auto s = client.getStatus();
        std::cout << "  Total: " << s.total
                  << "  |  Available: " << GREEN << s.available << RESET
                  << "  |  Reserved: "  << RED   << s.reserved  << RESET << '\n';
    } catch (const ResourceManagerException& e) {
        std::cerr << RED << "Cannot reach server: " << e.what() << RESET << '\n';
        return 1;
    }

    // ── 2. All resources ──────────────────────────────────────────────────
    section(2, "All Resources");
    auto all = client.listResources();
    for (const auto& r : all)
        printResource(r);

    // ── 3. Available resources ────────────────────────────────────────────
    section(3, "Available Resources");
    auto available = client.listResources("available");
    if (available.empty()) {
        std::cout << "  " << RED << "No available resources." << RESET << '\n';
        return 0;
    }
    for (const auto& r : available)
        printResource(r);

    // ── 4. Reserve first two ──────────────────────────────────────────────
    section(4, "Reserving Resources");
    std::vector<ResourceIdentifier> toReserve;
    int count = static_cast<int>(std::min(available.size(), size_t{2}));
    for (int k = 0; k < count; ++k) {
        toReserve.push_back({available[k].resource_class,
                             available[k].name,
                             available[k].enumerator});
        std::cout << "  Requesting: " << available[k].resource_class
                  << ':' << available[k].name
                  << ':' << available[k].enumerator << '\n';
    }

    auto result = client.reserve(CLIENT_ID, toReserve);
    if (result.success) {
        std::cout << '\n' << GREEN << "✓ " << result.message << RESET << '\n';
        for (const auto& r : result.resources)
            printResource(r);
    } else {
        std::cout << '\n' << RED << "✗ " << result.message << RESET << '\n';
        return 1;
    }

    // ── 5. Attempt double-reservation ─────────────────────────────────────
    section(5, "Attempting Double-Reservation (Expected Error)");
    std::cout << "  Requesting: " << toReserve[0].resource_class
              << ':' << toReserve[0].name << ':' << toReserve[0].enumerator
              << " as 'another-client'\n";

    auto conflictResult = client.reserve("another-client", {toReserve[0]});
    if (!conflictResult.success) {
        std::cout << '\n' << RED << "✓ Got expected error:\n"
                  << "  " << conflictResult.message << RESET << '\n';
        for (const auto& r : conflictResult.resources)
            printResource(r);
    } else {
        std::cout << YELLOW << "  Unexpected success — server did not detect conflict." << RESET << '\n';
    }

    // ── 6. Attempt non-existent resource ──────────────────────────────────
    section(6, "Attempting Non-Existent Resource (Expected Error)");
    std::cout << "  Requesting: BOGUS:FAKE:99\n";
    auto nonexist = client.reserve(CLIENT_ID, {{"BOGUS", "FAKE", "99"}});
    if (!nonexist.success)
        std::cout << '\n' << RED << "✓ Got expected error:\n  " << nonexist.message << RESET << '\n';

    // ── 7. Current state ──────────────────────────────────────────────────
    section(7, "Current Resource State (Mixed)");
    for (const auto& r : client.listResources())
        printResource(r);

    // ── 8. Release ───────────────────────────────────────────────────────
    section(8, "Releasing Reserved Resources");
    for (const auto& id : toReserve)
        std::cout << "  Releasing: " << id.resource_class << ':' << id.name << ':' << id.enumerator << '\n';

    std::string errMsg;
    if (client.release(CLIENT_ID, toReserve, errMsg)) {
        std::cout << '\n' << GREEN << "✓ Resources released successfully." << RESET << '\n';
    } else {
        std::cout << '\n' << RED << "✗ " << errMsg << RESET << '\n';
    }

    // ── 9. Final state ────────────────────────────────────────────────────
    section(9, "Final Resource State");
    for (const auto& r : client.listResources())
        printResource(r);

    auto finalStatus = client.getStatus();
    std::cout << "\n  " << BOLD << "Final Status:" << RESET
              << "  Total: " << finalStatus.total
              << "  |  Available: " << GREEN << finalStatus.available << RESET
              << "  |  Reserved: "  << RED   << finalStatus.reserved  << RESET << '\n';

    std::cout << '\n' << GREEN << "Demo complete." << RESET << "\n\n";
    return 0;
}
