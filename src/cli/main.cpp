#include "ResourceManagerClient.h"

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace mu2e;

// ── ANSI colours ─────────────────────────────────────────────────────────────

static const char* GREEN  = "\033[32m";
static const char* RED    = "\033[31m";
static const char* YELLOW = "\033[33m";
static const char* BOLD   = "\033[1m";
static const char* RESET  = "\033[0m";

// ── Formatting helpers ────────────────────────────────────────────────────────

static std::string statusStr(const std::string& s)
{
    if (s == "available") return std::string(GREEN) + s + RESET;
    if (s == "reserved")  return std::string(RED)   + s + RESET;
    return s;
}

static std::string portList(const Resource& r)
{
    std::string p;
    for (size_t i = 0; i < r.location.ports.size(); ++i) {
        if (i) p += ',';
        p += std::to_string(r.location.ports[i]);
    }
    return p;
}

static void printHeader()
{
    std::cout << '\n'
              << BOLD
              << std::left
              << "  " << std::setw(14) << "CLASS"
              << std::setw(12) << "NAME"
              << std::setw(6)  << "#"
              << std::setw(28) << "NODE"
              << std::setw(14) << "USER"
              << std::setw(22) << "PORTS"
              << "STATUS / OWNER / WHO"
              << RESET << '\n'
              << "  " << std::string(118, '-') << '\n';
}

static void printResource(const Resource& r)
{
    std::string ownerPart;
    if (!r.owner.empty())
        ownerPart = std::string("  (") + YELLOW + r.owner + RESET + ")";

    std::string whoPart;
    if (!r.who.empty())
        whoPart = std::string("  [") + YELLOW + r.who + RESET + "]";

    std::cout << std::left
              << "  " << std::setw(14) << r.resource_class
              << std::setw(12) << r.name
              << std::setw(6)  << r.enumerator
              << std::setw(28) << r.location.node
              << std::setw(14) << r.location.user
              << std::setw(22) << portList(r)
              << statusStr(r.status) << ownerPart << whoPart << '\n';
}

static void printUsage(const char* prog)
{
    std::cerr
        << "Usage: " << prog << " [--host HOST] [--port PORT] [--token TOKEN] [--who NAME]\n"
        << "            [--discovery-port PORT] [--no-discover] COMMAND [args]\n\n"
        << "  --host HOST        Server host. If unset, located via broadcast discovery.\n"
        << "  --token TOKEN      Bearer token for reserve/release (or set RM_TOKEN)\n"
        << "  --who NAME         Optional operator annotation ('Who' column; or set RM_WHO)\n"
        << "  --discovery-port P UDP discovery port (default 8088; or set RM_DISCOVERY_PORT)\n"
        << "  --no-discover      Do not broadcast-discover when --host is unset\n\n"
        << "Commands:\n"
        << "  list [--status available|reserved]     List resources\n"
        << "  get  <class> <name> <enum>             Get a specific resource\n"
        << "  reserve  <cls> <name> <enum> [...]     Reserve resources\n"
        << "  release  <cls> <name> <enum> [...]     Release resources\n"
        << "  release-all  <client-id>               Release all for a client\n"
        << "  status                                 Show server status\n\n"
        << "Examples:\n"
        << "  " << prog << " list\n"
        << "  " << prog << " list --status available\n"
        << "  " << prog << " get DTC DTC 01\n"
        << "  " << prog << " reserve DTC DTC 01\n"
        << "  " << prog << " --who Andrew reserve DTC DTC 01 CFO CFO 01\n"
        << "  " << prog << " release DTC DTC 01\n"
        << "  " << prog << " release-all partition1\n"
        << "  " << prog << " status\n";
}

// ── Argument parsing helpers ──────────────────────────────────────────────────

static std::vector<ResourceIdentifier>
parseTriples(const std::vector<std::string>& tokens, size_t start)
{
    std::vector<ResourceIdentifier> ids;
    for (size_t i = start; i + 2 < tokens.size(); i += 3) {
        ids.push_back({tokens[i], tokens[i + 1], tokens[i + 2]});
    }
    return ids;
}

// ── main ──────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[])
{
    std::string host;
    bool        hostSet = false;
    int         port = 0;
    int         discoveryPort = 8088;
    bool        noDiscover = false;
    std::string token;
    std::string who;
    if (const char* envHost = std::getenv("RM_HOST")) { host = envHost; hostSet = true; }
    if (const char* envPort = std::getenv("RM_PORT")) port = std::stoi(envPort);
    if (const char* envDp = std::getenv("RM_DISCOVERY_PORT")) discoveryPort = std::stoi(envDp);
    if (const char* envTok = std::getenv("RM_TOKEN")) token = envTok;
    if (const char* envWho = std::getenv("RM_WHO")) who = envWho;

    // Collect raw args
    std::vector<std::string> args(argv + 1, argv + argc);
    size_t i = 0;

    // Global options
    while (i < args.size() && args[i].rfind("--", 0) == 0) {
        if (args[i] == "--host" && i + 1 < args.size()) {
            host = args[++i];
            hostSet = true;
        } else if (args[i] == "--port" && i + 1 < args.size()) {
            port = std::stoi(args[++i]);
        } else if (args[i] == "--token" && i + 1 < args.size()) {
            token = args[++i];
        } else if (args[i] == "--who" && i + 1 < args.size()) {
            who = args[++i];
        } else if (args[i] == "--discovery-port" && i + 1 < args.size()) {
            discoveryPort = std::stoi(args[++i]);
        } else if (args[i] == "--no-discover") {
            noDiscover = true;
        } else {
            break;
        }
        ++i;
    }

    // Locate the server via broadcast discovery when --host is not set.
    if (!hostSet && !noDiscover) {
        auto found = ResourceManagerClient::discover(discoveryPort);
        if (found) {
            host = found->first;
            if (port == 0) port = found->second;
            std::cerr << YELLOW << "Discovered resource manager at "
                      << host << ":" << port << RESET << '\n';
        }
    }
    if (host.empty()) host = "localhost";
    if (port == 0)    port = 8080;

    if (i >= args.size()) {
        printUsage(argv[0]);
        return 1;
    }

    const std::string command = args[i++];

    try {
        ResourceManagerClient client(host, port, token);

        // ── list ─────────────────────────────────────────────────────────
        if (command == "list") {
            std::string statusFilter;
            if (i < args.size() && args[i] == "--status" && i + 1 < args.size())
                statusFilter = args[i + 1];

            auto resources = client.listResources(statusFilter);
            printHeader();
            for (const auto& r : resources)
                printResource(r);
            std::cout << "\n  " << resources.size() << " resource(s).\n\n";

        // ── get ──────────────────────────────────────────────────────────
        } else if (command == "get") {
            if (i + 2 >= args.size()) {
                std::cerr << RED << "Usage: get <class> <name> <enumerator>" << RESET << '\n';
                return 1;
            }
            auto r = client.getResource(args[i], args[i + 1], args[i + 2]);
            if (!r) {
                std::cerr << RED << "Resource not found: "
                          << args[i] << ':' << args[i+1] << ':' << args[i+2]
                          << RESET << '\n';
                return 1;
            }
            printHeader();
            printResource(*r);
            std::cout << '\n';

        // ── reserve ──────────────────────────────────────────────────────
        } else if (command == "reserve") {
            size_t remaining = args.size() - i;
            if (remaining == 0 || remaining % 3 != 0) {
                std::cerr << RED << "Resource arguments must be given as complete "
                             "<class> <name> <enum> triples." << RESET << '\n';
                return 1;
            }
            auto ids = parseTriples(args, i);
            auto result = client.reserve("", ids, who);
            if (result.success) {
                std::cout << GREEN << "✓ " << result.message << RESET << '\n';
                printHeader();
                for (const auto& r : result.resources)
                    printResource(r);
                std::cout << '\n';
            } else {
                std::cerr << RED << "✗ " << result.message << RESET << '\n';
                if (!result.resources.empty()) {
                    std::cout << "Conflicting resource(s):\n";
                    printHeader();
                    for (const auto& r : result.resources)
                        printResource(r);
                    std::cout << '\n';
                }
                return 1;
            }

        // ── release ──────────────────────────────────────────────────────
        } else if (command == "release") {
            size_t remaining = args.size() - i;
            if (remaining == 0 || remaining % 3 != 0) {
                std::cerr << RED << "Resource arguments must be given as complete "
                             "<class> <name> <enum> triples." << RESET << '\n';
                return 1;
            }
            auto ids = parseTriples(args, i);
            std::string errMsg;
            if (client.release("", ids, errMsg)) {
                std::cout << GREEN << "✓ Resources released successfully." << RESET << '\n';
            } else {
                std::cerr << RED << "✗ " << errMsg << RESET << '\n';
                return 1;
            }

        // ── release-all ──────────────────────────────────────────────────
        } else if (command == "release-all") {
            if (i >= args.size()) {
                std::cerr << RED << "Usage: release-all <client-id>" << RESET << '\n';
                return 1;
            }
            int count = client.releaseAll(args[i]);
            std::cout << GREEN << "✓ Released " << count
                      << " resource(s) for '" << args[i] << "'." << RESET << '\n';

        // ── status ───────────────────────────────────────────────────────
        } else if (command == "status") {
            auto s = client.getStatus();
            std::cout << '\n'
                      << BOLD << "Server Status" << RESET << '\n'
                      << "  Total:     " << s.total     << '\n'
                      << "  Available: " << GREEN << s.available << RESET << '\n'
                      << "  Reserved:  " << RED   << s.reserved  << RESET << "\n\n";

        } else {
            std::cerr << RED << "Unknown command: " << command << RESET << '\n';
            printUsage(argv[0]);
            return 1;
        }

    } catch (const ResourceManagerException& e) {
        std::cerr << RED << "Error: " << e.what() << RESET << '\n';
        return 1;
    } catch (const std::exception& e) {
        std::cerr << RED << "Fatal: " << e.what() << RESET << '\n';
        return 1;
    }

    return 0;
}
