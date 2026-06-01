/**
 * WeChat Article Agent — C++ HTTP 客户端示例（Windows WinHTTP）
 *
 * 编译（Visual Studio 开发者命令行）:
 *   cl /EHsc /std:c++17 wechat_agent_client.cpp winhttp.lib
 *
 * 用法:
 *   wechat_agent_client.exe http://127.0.0.1:8780 your-api-key
 *
 * 嵌入 C++ 编程平台：将 triggerWeChatDraft() 在用户提交资料或定时任务时调用即可。
 * Agent 服务独立进程运行，C++ 侧只发 HTTP，无需嵌入 Python。
 */

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winhttp.h>

#include <iostream>
#include <string>

#pragma comment(lib, "winhttp.lib")

static std::wstring toWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    std::wstring out(n - 1, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, out.data(), n);
    return out;
}

static std::string httpPostJson(
    const std::wstring& host,
    INTERNET_PORT port,
    const std::wstring& path,
    const std::string& jsonBody,
    const std::wstring& apiKey) {

    HINTERNET session = WinHttpOpen(L"WeChatAgentCpp/1.0",
        WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
        WINHTTP_NO_PROXY_NAME,
        WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) throw std::runtime_error("WinHttpOpen failed");

    HINTERNET connect = WinHttpConnect(session, host.c_str(), port, 0);
    if (!connect) {
        WinHttpCloseHandle(session);
        throw std::runtime_error("WinHttpConnect failed");
    }

    HINTERNET request = WinHttpOpenRequest(
        connect, L"POST", path.c_str(),
        nullptr, WINHTTP_NO_REFERER,
        WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!request) {
        WinHttpCloseHandle(connect);
        WinHttpCloseHandle(session);
        throw std::runtime_error("WinHttpOpenRequest failed");
    }

    std::wstring headers = L"Content-Type: application/json\r\nX-API-Key: " + apiKey + L"\r\n";
    BOOL ok = WinHttpSendRequest(
        request,
        headers.c_str(), (DWORD)-1L,
        (LPVOID)jsonBody.data(), (DWORD)jsonBody.size(),
        (DWORD)jsonBody.size(), 0);
    if (!ok || !WinHttpReceiveResponse(request, nullptr)) {
        WinHttpCloseHandle(request);
        WinHttpCloseHandle(connect);
        WinHttpCloseHandle(session);
        throw std::runtime_error("HTTP request failed");
    }

    std::string response;
    DWORD available = 0;
    do {
        if (!WinHttpQueryDataAvailable(request, &available)) break;
        if (available == 0) break;
        std::string chunk(available, '\0');
        DWORD read = 0;
        if (!WinHttpReadData(request, chunk.data(), available, &read)) break;
        chunk.resize(read);
        response += chunk;
    } while (available > 0);

    WinHttpCloseHandle(request);
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);
    return response;
}

/** 平台集成入口：触发「Markdown → 微信草稿」流水线 */
std::string triggerWeChatDraft(
    const std::string& baseUrl,
    const std::string& apiKey,
    const std::string& title,
    const std::string& markdownPath,
    const std::string& thumbPath) {

    // 解析 http://host:port
    std::wstring whost = L"127.0.0.1";
    INTERNET_PORT wport = 8780;
    if (baseUrl.find("http://") == 0) {
        auto rest = baseUrl.substr(7);
        auto colon = rest.find(':');
        if (colon != std::string::npos) {
            whost = toWide(rest.substr(0, colon));
            wport = (INTERNET_PORT)std::stoi(rest.substr(colon + 1));
        } else {
            whost = toWide(rest);
        }
    }

    std::string body = R"({
  "title": ")" + title + R"(",
  "markdown_path": ")" + markdownPath + R"(",
  "thumb_path": ")" + thumbPath + R"(",
  "publish": false,
  "async_mode": true
})";

    return httpPostJson(whost, wport, L"/api/v1/webhook", body, toWide(apiKey));
}

int main(int argc, char* argv[]) {
    std::string base = argc > 1 ? argv[1] : "http://127.0.0.1:8780";
    std::string key = argc > 2 ? argv[2] : "change-me-to-a-long-random-secret";

    try {
        auto resp = triggerWeChatDraft(
            base, key,
            "示例文章标题",
            "articles/example.md",
            "articles/diagrams/cover.png");
        std::cout << resp << std::endl;
        std::cout << "Poll job status: GET " << base << "/api/v1/jobs/{job_id}" << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return 1;
    }
    return 0;
}
