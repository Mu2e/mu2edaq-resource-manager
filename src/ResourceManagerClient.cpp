#include "ResourceManagerClient.h"

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <cstring>
#include <mutex>
#include <sstream>
#include <stdexcept>

#ifdef _WIN32
#  include <winsock2.h>
#  include <ws2tcpip.h>
#else
#  include <arpa/inet.h>
#  include <netinet/in.h>
#  include <sys/socket.h>
#  include <sys/time.h>
#  include <unistd.h>
#endif

using json = nlohmann::json;

namespace mu2e {

// Discovery protocol constant — must match server/discovery.py.
static const char* kDiscoveryMagic = "MU2E-RM-DISCOVER-V1";

// libcurl global init/cleanup are process-wide lifecycle calls, not per-object.
// Initialize exactly once for the whole process on first client construction.
// We deliberately do not call curl_global_cleanup() per instance (or at all):
// tying it to a single client could deinitialize libcurl while other clients or
// unrelated libcurl users in the same process are still active. The OS reclaims
// the process-wide resources at exit.
static void ensureCurlInitialized()
{
    static std::once_flag curl_init_flag;
    std::call_once(curl_init_flag, []() {
        curl_global_init(CURL_GLOBAL_DEFAULT);
    });
}

// ── Helpers ──────────────────────────────────────────────────────────────────

// Optional string field that may be absent or JSON null (e.g. owner/who on an
// available resource). nlohmann's value() throws on null, so handle it here.
static std::string optString(const json& j, const char* key)
{
    auto it = j.find(key);
    if (it == j.end() || it->is_null())
        return "";
    return it->get<std::string>();
}

static Resource parseResource(const json& j)
{
    Resource r;
    r.resource_class = j.at("resource_class").get<std::string>();
    r.name           = j.at("name").get<std::string>();
    r.enumerator     = j.at("enumerator").get<std::string>();
    r.status         = j.at("status").get<std::string>();
    r.owner          = optString(j, "owner");
    r.who            = optString(j, "who");

    auto& loc           = j.at("location");
    r.location.node      = loc.at("node").get<std::string>();
    r.location.user      = loc.at("user").get<std::string>();
    r.location.ports_any = loc.value("ports_any", false);
    for (const auto& p : loc.at("ports"))
        r.location.ports.push_back(p.get<int>());

    return r;
}

static json resourceIdentifierToJson(const ResourceIdentifier& id)
{
    return json{
        {"resource_class", id.resource_class},
        {"name",           id.name},
        {"enumerator",     id.enumerator},
    };
}

// ── CURL callback ─────────────────────────────────────────────────────────────

size_t ResourceManagerClient::writeCallback(void* contents, size_t size,
                                             size_t nmemb, std::string* out)
{
    out->append(static_cast<char*>(contents), size * nmemb);
    return size * nmemb;
}

// ── Construction ──────────────────────────────────────────────────────────────

ResourceManagerClient::ResourceManagerClient(const std::string& host, int port,
                                             const std::string& token)
    : base_url_("http://" + host + ":" + std::to_string(port))
    , auth_token_(token)
{
    ensureCurlInitialized();
}

ResourceManagerClient::~ResourceManagerClient() = default;

// ── HTTP primitives ───────────────────────────────────────────────────────────

HttpResponse ResourceManagerClient::httpGet(const std::string& path)
{
    CURL* curl = curl_easy_init();
    if (!curl)
        throw ResourceManagerException("curl_easy_init() failed");

    HttpResponse resp;
    std::string  url = base_url_ + path;

    curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &resp.body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,       10L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &resp.status_code);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK)
        throw ResourceManagerException(std::string("HTTP GET failed: ") + curl_easy_strerror(res));

    return resp;
}

HttpResponse ResourceManagerClient::httpPost(const std::string& path,
                                              const std::string& body)
{
    CURL* curl = curl_easy_init();
    if (!curl)
        throw ResourceManagerException("curl_easy_init() failed");

    HttpResponse resp;
    std::string  url = base_url_ + path;

    curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");
    if (!auth_token_.empty())
        headers = curl_slist_append(headers, ("Authorization: Bearer " + auth_token_).c_str());

    curl_easy_setopt(curl, CURLOPT_URL,           url.c_str());
    curl_easy_setopt(curl, CURLOPT_POST,          1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS,    body.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER,    headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,     &resp.body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,       10L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &resp.status_code);
    curl_easy_cleanup(curl);
    curl_slist_free_all(headers);

    if (res != CURLE_OK)
        throw ResourceManagerException(std::string("HTTP POST failed: ") + curl_easy_strerror(res));

    return resp;
}

HttpResponse ResourceManagerClient::httpDelete(const std::string& path)
{
    CURL* curl = curl_easy_init();
    if (!curl)
        throw ResourceManagerException("curl_easy_init() failed");

    HttpResponse resp;
    std::string  url = base_url_ + path;

    curl_slist* headers = nullptr;
    if (!auth_token_.empty())
        headers = curl_slist_append(headers, ("Authorization: Bearer " + auth_token_).c_str());

    curl_easy_setopt(curl, CURLOPT_URL,            url.c_str());
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST,  "DELETE");
    if (headers)
        curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION,  writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,      &resp.body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,        10L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &resp.status_code);
    curl_easy_cleanup(curl);
    curl_slist_free_all(headers);

    if (res != CURLE_OK)
        throw ResourceManagerException(std::string("HTTP DELETE failed: ") + curl_easy_strerror(res));

    return resp;
}

// ── Public API ────────────────────────────────────────────────────────────────

std::vector<Resource>
ResourceManagerClient::listResources(const std::string& status)
{
    std::string path = "/api/resources";
    if (!status.empty())
        path += "?status=" + status;

    auto resp = httpGet(path);
    if (!resp.ok())
        throw ResourceManagerException("listResources failed: " + resp.body);

    auto j = json::parse(resp.body);
    std::vector<Resource> result;
    for (const auto& item : j)
        result.push_back(parseResource(item));
    return result;
}

std::optional<Resource>
ResourceManagerClient::getResource(const std::string& resource_class,
                                    const std::string& name,
                                    const std::string& enumerator)
{
    auto resp = httpGet("/api/resources/" + resource_class + "/" + name + "/" + enumerator);
    if (resp.status_code == 404)
        return std::nullopt;
    if (!resp.ok())
        throw ResourceManagerException("getResource failed: " + resp.body);
    return parseResource(json::parse(resp.body));
}

ReservationResult
ResourceManagerClient::reserve(const std::string&                   client_id,
                                const std::vector<ResourceIdentifier>& resources,
                                const std::string&                   who)
{
    json req;
    req["client_id"] = client_id;
    req["who"]       = who.empty() ? json(nullptr) : json(who);
    req["resources"] = json::array();
    for (const auto& r : resources)
        req["resources"].push_back(resourceIdentifierToJson(r));

    auto resp = httpPost("/api/reserve", req.dump());

    ReservationResult result;
    if (resp.ok()) {
        auto j           = json::parse(resp.body);
        result.success   = true;
        result.message   = j.at("message").get<std::string>();
        for (const auto& item : j.at("resources"))
            result.resources.push_back(parseResource(item));
    } else {
        result.success = false;
        try {
            auto j = json::parse(resp.body);
            auto detail = j.value("detail", json{});
            if (detail.is_object()) {
                result.message = detail.value("message", resp.body);
                for (const auto& item : detail.value("resources", json::array()))
                    result.resources.push_back(parseResource(item));
            } else {
                result.message = detail.is_string() ? detail.get<std::string>() : resp.body;
            }
        } catch (...) {
            result.message = resp.body;
        }
    }
    return result;
}

bool ResourceManagerClient::release(const std::string&                   client_id,
                                     const std::vector<ResourceIdentifier>& resources,
                                     std::string&                           error_out)
{
    json req;
    req["client_id"] = client_id;
    req["resources"] = json::array();
    for (const auto& r : resources)
        req["resources"].push_back(resourceIdentifierToJson(r));

    auto resp = httpPost("/api/release", req.dump());
    if (resp.ok())
        return true;

    try {
        auto j  = json::parse(resp.body);
        auto d  = j.value("detail", json{});
        error_out = d.is_string() ? d.get<std::string>() : resp.body;
    } catch (...) {
        error_out = resp.body;
    }
    return false;
}

int ResourceManagerClient::releaseAll(const std::string& client_id)
{
    auto resp = httpDelete("/api/clients/" + client_id + "/resources");
    if (!resp.ok())
        return 0;
    try {
        auto j = json::parse(resp.body);
        return j.value("count", 0);
    } catch (...) {
        return 0;
    }
}

ServerStatus ResourceManagerClient::getStatus()
{
    auto resp = httpGet("/api/status");
    if (!resp.ok())
        throw ResourceManagerException("getStatus failed: " + resp.body);
    auto j = json::parse(resp.body);
    return ServerStatus{
        j.at("total").get<int>(),
        j.at("available").get<int>(),
        j.at("reserved").get<int>(),
    };
}

// ── Discovery ───────────────────────────────────────────────────────────────

std::optional<std::pair<std::string, int>>
ResourceManagerClient::discover(int discovery_port, int timeout_ms)
{
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
        return std::nullopt;
    SOCKET sock = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sock == INVALID_SOCKET) { WSACleanup(); return std::nullopt; }
#else
    int sock = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0)
        return std::nullopt;
#endif

    int broadcast = 1;
    ::setsockopt(sock, SOL_SOCKET, SO_BROADCAST,
                 reinterpret_cast<const char*>(&broadcast), sizeof(broadcast));

#ifdef _WIN32
    DWORD tv = static_cast<DWORD>(timeout_ms);
    ::setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, reinterpret_cast<const char*>(&tv), sizeof(tv));
#else
    struct timeval tv;
    tv.tv_sec  = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;
    ::setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
#endif

    sockaddr_in dest{};
    dest.sin_family      = AF_INET;
    dest.sin_port        = htons(static_cast<unsigned short>(discovery_port));
    dest.sin_addr.s_addr = htonl(INADDR_BROADCAST);

    ::sendto(sock, kDiscoveryMagic, static_cast<int>(std::strlen(kDiscoveryMagic)), 0,
             reinterpret_cast<sockaddr*>(&dest), sizeof(dest));

    std::optional<std::pair<std::string, int>> result;
    char buf[1024];
    for (;;) {
        int n = static_cast<int>(::recvfrom(sock, buf, sizeof(buf) - 1, 0, nullptr, nullptr));
        if (n <= 0)
            break;  // timeout or error
        buf[n] = '\0';
        try {
            auto j = json::parse(buf);
            if (j.value("service", std::string()) == "mu2e-resource-manager"
                && j.contains("host") && j.contains("port")) {
                result = std::make_pair(j.at("host").get<std::string>(),
                                        j.at("port").get<int>());
                break;
            }
        } catch (...) {
            continue;
        }
    }

#ifdef _WIN32
    closesocket(sock);
    WSACleanup();
#else
    ::close(sock);
#endif
    return result;
}

} // namespace mu2e
