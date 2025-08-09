#include <windows.h>
#include <dxgi.h>
#include <iostream>
#include <string>
#include <vector>

#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "ole32.lib")

std::string WideStringToUtf8(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    int size_needed = WideCharToMultiByte(CP_UTF8, 0, wstr.data(), (int)wstr.size(), NULL, 0, NULL, NULL);
    std::string strTo(size_needed, 0);
    WideCharToMultiByte(CP_UTF8, 0, wstr.data(), (int)wstr.size(), strTo.data(), size_needed, NULL, NULL);
    return strTo;
}

int main() {
    IDXGIFactory* pFactory = nullptr;
    if (FAILED(CreateDXGIFactory(__uuidof(IDXGIFactory), (void**)&pFactory))) {
        std::cerr << "Failed to create DXGIFactory\n";
        return -1;
    }

    std::vector<std::wstring> gpuNames;
    std::vector<SIZE_T> dedicatedVRAMs;
    std::vector<SIZE_T> dedicatedSystemMemorys;
    std::vector<SIZE_T> sharedSystemMemorys;

    UINT index = 0;
    IDXGIAdapter* pAdapter = nullptr;
    std::cout << "{\n  \"gpus\": [\n";

    bool first = true;
    while (pFactory->EnumAdapters(index, &pAdapter) != DXGI_ERROR_NOT_FOUND) {
        DXGI_ADAPTER_DESC desc;
        pAdapter->GetDesc(&desc);

        std::string nameUtf8 = WideStringToUtf8(desc.Description);
        double vramGB = static_cast<double>(desc.DedicatedVideoMemory) / (1024.0 * 1024.0 * 1024.0);
        unsigned long long dedicatedSysMB = desc.DedicatedSystemMemory / (1024 * 1024);
        unsigned long long sharedSysMB = desc.SharedSystemMemory / (1024 * 1024);

        if (!first) std::cout << ",\n";
        first = false;

        std::cout << "    {\n";
        std::cout << "      \"name\": \"" << nameUtf8 << "\",\n";
        std::cout << "      \"dedicatedVRAM_GB\": " << vramGB << ",\n";
        std::cout << "      \"dedicatedSystemMemory_MB\": " << dedicatedSysMB << ",\n";
        std::cout << "      \"sharedSystemMemory_MB\": " << sharedSysMB << "\n";
        std::cout << "    }";

        pAdapter->Release();
        index++;
    }

    std::cout << "\n  ]\n}\n";

    pFactory->Release();
    return 0;
}
