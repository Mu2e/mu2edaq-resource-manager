#include "ResourceManagerClient.h"

#include <curl/curl.h>
#include <nlohmann/json.hpp>

#include <sstream>
#include <stdexcept>

using json = nlohmann::json;

namespace mu2e {

// ── Helpers ──────────────────────────────────────────────────────────────────

static Resource parseResource(const json& j)
{
    Resource r;
    r.resource_class = j.at("resource_class").get<std::string>();
    r.name           = j.at("name").get<std::string>();
    r.enumerator     = j.at("enumerator").get<std::string>();
    r.status         = j.at("status").get<std::string>();
    r.owner          = j.value("owner", "");

    auto& loc        = j.at("location");
    r.location.node  = loc.at("node").get<std::string>();
    r.location.user  = loc.at("user").get<std::string>();
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

ResourceManagerClient::ResourceManagerClient(const std::string& host, int port)
    : base_url_("http://" + host + ":" + std::to_string(port))
{
    curl_global_init(CURL_GLOBAL_DEFAULT);
}

ResourceManagerClient::~ResourceManagerClient()
{
    curl_global_cleanup();
}

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

    curl_easy_setopt(curl, CURLOPT_URL,            url.c_str());
    curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST,  "DELETE");
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION,  writeCallback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA,      &resp.body);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT,        10L);

    CURLcode res = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &resp.status_code);
    curl_easy_cleanup(curl);

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
                                const std::vector<ResourceIdentifier>& resources)
{
    json req;
    req["client_id"] = client_id;
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

} // namespace mu2e
