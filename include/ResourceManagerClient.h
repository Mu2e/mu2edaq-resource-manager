#pragma once

#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace mu2e {

// ── Data structures ──────────────────────────────────────────────────────────

struct Location {
    std::string node;
    std::string user;
    std::vector<int> ports;
};

struct Resource {
    std::string resource_class;
    std::string name;
    std::string enumerator;
    Location    location;
    std::string status;   // "available" | "reserved"
    std::string owner;    // authenticated principal; empty when not reserved
    std::string who;      // free-text operator annotation; empty when not set
};

struct ResourceIdentifier {
    std::string resource_class;
    std::string name;
    std::string enumerator;
};

struct ReservationResult {
    bool                  success;
    std::string           message;
    std::vector<Resource> resources;  // reserved on success, conflicting on failure
};

struct ServerStatus {
    int total;
    int available;
    int reserved;
};

// Internal HTTP response (status_code + body)
struct HttpResponse {
    long        status_code{0};
    std::string body;
    bool ok() const { return status_code >= 200 && status_code < 300; }
};

// ── Exception ────────────────────────────────────────────────────────────────

class ResourceManagerException : public std::runtime_error {
public:
    explicit ResourceManagerException(const std::string& msg)
        : std::runtime_error(msg) {}
};

// ── Client ───────────────────────────────────────────────────────────────────

class ResourceManagerClient {
public:
    /**
     * Construct a client targeting the given host and port.
     *
     * If a bearer token is supplied it is sent as an Authorization header on
     * state-changing requests (reserve/release/release-all); read-only calls do
     * not require it.
     *
     * libcurl's process-wide global state is initialized once, on first client
     * construction, in a thread-safe manner. It is intentionally never cleaned
     * up per instance, so constructing or destroying one client never affects
     * other clients or unrelated libcurl users in the same process.
     */
    explicit ResourceManagerClient(const std::string& host = "localhost", int port = 8080,
                                   const std::string& token = "");
    ~ResourceManagerClient();

    /** Set or replace the bearer token sent on state-changing requests. */
    void setAuthToken(const std::string& token) { auth_token_ = token; }

    /**
     * Locate a resource manager via UDP broadcast discovery.
     * Broadcasts on the given discovery port and waits up to timeout_ms for a
     * reply. Returns {host, port} of the HTTP API, or std::nullopt on timeout.
     */
    static std::optional<std::pair<std::string, int>>
    discover(int discovery_port = 8088, int timeout_ms = 2000);

    // Non-copyable, movable
    ResourceManagerClient(const ResourceManagerClient&)            = delete;
    ResourceManagerClient& operator=(const ResourceManagerClient&) = delete;
    ResourceManagerClient(ResourceManagerClient&&)                 = default;
    ResourceManagerClient& operator=(ResourceManagerClient&&)      = default;

    /** List all resources, optionally filtered by status ("available" | "reserved"). */
    std::vector<Resource> listResources(const std::string& status = "");

    /** Get a specific resource by class, name, and enumerator. */
    std::optional<Resource> getResource(const std::string& resource_class,
                                        const std::string& name,
                                        const std::string& enumerator);

    /** Reserve one or more resources.  All-or-nothing.
     *  The owner is the authenticated principal (from the bearer token);
     *  client_id is accepted for compatibility but ignored by the server.
     *  who is an optional free-text operator annotation (the "Who" column). */
    ReservationResult reserve(const std::string&                   client_id,
                              const std::vector<ResourceIdentifier>& resources,
                              const std::string&                   who = "");

    /** Release one or more resources owned by client_id. */
    bool release(const std::string&                   client_id,
                 const std::vector<ResourceIdentifier>& resources,
                 std::string&                           error_out);

    /** Release every resource held by client_id. Returns the count released. */
    int releaseAll(const std::string& client_id);

    /** Get server summary statistics. */
    ServerStatus getStatus();

private:
    std::string base_url_;
    std::string auth_token_;

    HttpResponse httpGet(const std::string& path);
    HttpResponse httpPost(const std::string& path, const std::string& body);
    HttpResponse httpDelete(const std::string& path);

    static size_t writeCallback(void* contents, size_t size, size_t nmemb,
                                std::string* out);
};

} // namespace mu2e
