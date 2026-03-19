#pragma once

#include <optional>
#include <stdexcept>
#include <string>
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
    std::string owner;    // empty when not reserved
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
     * curl_global_init() is called here; the destructor calls curl_global_cleanup().
     */
    explicit ResourceManagerClient(const std::string& host = "localhost", int port = 8080);
    ~ResourceManagerClient();

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

    /** Reserve one or more resources for client_id.  All-or-nothing. */
    ReservationResult reserve(const std::string&                   client_id,
                              const std::vector<ResourceIdentifier>& resources);

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

    HttpResponse httpGet(const std::string& path);
    HttpResponse httpPost(const std::string& path, const std::string& body);
    HttpResponse httpDelete(const std::string& path);

    static size_t writeCallback(void* contents, size_t size, size_t nmemb,
                                std::string* out);
};

} // namespace mu2e
