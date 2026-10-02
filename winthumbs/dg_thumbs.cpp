// DocGuard: miniaturas de los PDF en el Explorador de Windows con su estado (firmado,
// contraseña, censurado, protegido). Lee el PDF que le pasa el Explorador, decide el estado
// igual que status_icons.py y devuelve la imagen correspondiente de iconos_estado\ (junto a la DLL).
// Se registra solo para el usuario (HKCU), sin permisos de administrador.

#include <windows.h>
#include <shlwapi.h>
#include <thumbcache.h>
#include <wincodec.h>
#include <new>
#include <string>

// {7A3E6C2B-4F1D-4C8B-9B8E-2D1F5A6C9E31}
static const CLSID CLSID_DGThumbs = {0x7a3e6c2b, 0x4f1d, 0x4c8b, {0x9b, 0x8e, 0x2d, 0x1f, 0x5a, 0x6c, 0x9e, 0x31}};
static HMODULE g_module = nullptr;
static long g_objects = 0;
static long g_locks = 0;

static bool contains(const std::string& s, const char* what) { return s.find(what) != std::string::npos; }

// Mismo criterio que status_icons.status()
static std::wstring icon_name(const std::string& data) {
    std::wstring n = L"pdf";
    if (contains(data, "/ByteRange") && (contains(data, "/Type/Sig") || contains(data, "/Type /Sig"))) n += L"_firmado";
    size_t tail = data.size() > 200000 ? data.size() - 200000 : 0;
    if (data.find("/Encrypt", tail) != std::string::npos || data.substr(0, 4096).find("/Encrypt") != std::string::npos) n += L"_contrasena";
    if (contains(data, "/DocGuardCensurado")) n += L"_censurado";
    if (contains(data, "/DocGuardProtegido")) n += L"_protegido";
    return n;
}

static HRESULT load_png(const std::wstring& path, UINT cx, HBITMAP* out) {
    IWICImagingFactory* f = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&f));
    if (FAILED(hr)) return hr;
    IWICBitmapDecoder* dec = nullptr;
    IWICBitmapFrameDecode* frame = nullptr;
    IWICBitmapScaler* scaler = nullptr;
    IWICFormatConverter* conv = nullptr;
    hr = f->CreateDecoderFromFilename(path.c_str(), nullptr, GENERIC_READ, WICDecodeMetadataCacheOnDemand, &dec);
    if (SUCCEEDED(hr)) hr = dec->GetFrame(0, &frame);
    if (SUCCEEDED(hr)) hr = f->CreateBitmapScaler(&scaler);
    if (SUCCEEDED(hr)) hr = scaler->Initialize(frame, cx, cx, WICBitmapInterpolationModeFant);
    if (SUCCEEDED(hr)) hr = f->CreateFormatConverter(&conv);
    if (SUCCEEDED(hr)) hr = conv->Initialize(scaler, GUID_WICPixelFormat32bppPBGRA, WICBitmapDitherTypeNone, nullptr, 0, WICBitmapPaletteTypeCustom);
    if (SUCCEEDED(hr)) {
        BITMAPINFO bmi = {};
        bmi.bmiHeader.biSize = sizeof(bmi.bmiHeader);
        bmi.bmiHeader.biWidth = (LONG)cx;
        bmi.bmiHeader.biHeight = -(LONG)cx;  // de arriba abajo
        bmi.bmiHeader.biPlanes = 1;
        bmi.bmiHeader.biBitCount = 32;
        bmi.bmiHeader.biCompression = BI_RGB;
        void* bits = nullptr;
        HBITMAP bmp = CreateDIBSection(nullptr, &bmi, DIB_RGB_COLORS, &bits, nullptr, 0);
        if (!bmp) hr = E_OUTOFMEMORY;
        else {
            hr = conv->CopyPixels(nullptr, cx * 4, cx * cx * 4, (BYTE*)bits);
            if (SUCCEEDED(hr)) *out = bmp; else DeleteObject(bmp);
        }
    }
    if (conv) conv->Release();
    if (scaler) scaler->Release();
    if (frame) frame->Release();
    if (dec) dec->Release();
    f->Release();
    return hr;
}

class Thumbs : public IInitializeWithStream, public IThumbnailProvider {
    long refs = 1;
    IStream* stream = nullptr;
public:
    Thumbs() { InterlockedIncrement(&g_objects); }
    virtual ~Thumbs() { if (stream) stream->Release(); InterlockedDecrement(&g_objects); }
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) {
        static const QITAB qit[] = {QITABENT(Thumbs, IInitializeWithStream), QITABENT(Thumbs, IThumbnailProvider), {0}};
        return QISearch(this, qit, riid, ppv);
    }
    IFACEMETHODIMP_(ULONG) AddRef() { return InterlockedIncrement(&refs); }
    IFACEMETHODIMP_(ULONG) Release() { long r = InterlockedDecrement(&refs); if (!r) delete this; return r; }
    IFACEMETHODIMP Initialize(IStream* s, DWORD) {
        if (stream) return HRESULT_FROM_WIN32(ERROR_ALREADY_INITIALIZED);
        stream = s;
        stream->AddRef();
        return S_OK;
    }
    IFACEMETHODIMP GetThumbnail(UINT cx, HBITMAP* phbmp, WTS_ALPHATYPE* alpha) {
        if (!stream || !phbmp) return E_UNEXPECTED;
        std::string data;
        char buf[65536];
        ULONG got = 0;
        while (data.size() < (64u << 20) && SUCCEEDED(stream->Read(buf, sizeof(buf), &got)) && got) data.append(buf, got);
        wchar_t dir[MAX_PATH];
        GetModuleFileNameW(g_module, dir, MAX_PATH);
        PathRemoveFileSpecW(dir);
        std::wstring path = std::wstring(dir) + L"\\iconos_estado\\" + icon_name(data) + L".png";
        HRESULT hr = load_png(path, cx ? cx : 256, phbmp);
        if (SUCCEEDED(hr) && alpha) *alpha = WTSAT_ARGB;
        return hr;
    }
};

class Factory : public IClassFactory {
    long refs = 1;
public:
    IFACEMETHODIMP QueryInterface(REFIID riid, void** ppv) {
        static const QITAB qit[] = {QITABENT(Factory, IClassFactory), {0}};
        return QISearch(this, qit, riid, ppv);
    }
    IFACEMETHODIMP_(ULONG) AddRef() { return InterlockedIncrement(&refs); }
    IFACEMETHODIMP_(ULONG) Release() { long r = InterlockedDecrement(&refs); if (!r) delete this; return r; }
    IFACEMETHODIMP CreateInstance(IUnknown* outer, REFIID riid, void** ppv) {
        if (outer) return CLASS_E_NOAGGREGATION;
        Thumbs* t = new (std::nothrow) Thumbs();
        if (!t) return E_OUTOFMEMORY;
        HRESULT hr = t->QueryInterface(riid, ppv);
        t->Release();
        return hr;
    }
    IFACEMETHODIMP LockServer(BOOL lock) { if (lock) InterlockedIncrement(&g_locks); else InterlockedDecrement(&g_locks); return S_OK; }
};

extern "C" BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { g_module = inst; DisableThreadLibraryCalls(inst); }
    return TRUE;
}

extern "C" HRESULT __stdcall DllGetClassObject(REFCLSID clsid, REFIID riid, void** ppv) {
    if (!IsEqualCLSID(clsid, CLSID_DGThumbs)) return CLASS_E_CLASSNOTAVAILABLE;
    Factory* f = new (std::nothrow) Factory();
    if (!f) return E_OUTOFMEMORY;
    HRESULT hr = f->QueryInterface(riid, ppv);
    f->Release();
    return hr;
}

extern "C" HRESULT __stdcall DllCanUnloadNow() { return (g_objects == 0 && g_locks == 0) ? S_OK : S_FALSE; }
