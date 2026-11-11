# silverfish-mclibrary

Bilgisayardaki belgeleri (.txt, .md, .pdf) Minecraft'ta yazılı kitaplara dönüştüren
bir Fabric modu ile Python servisi.

- `service/`: belgeleri okuyup kitap sayfalarına bölen FastAPI servisi
- `mod/`: Fabric modu (hazırlanıyor)

## Servis

### Kurulum (bir kez)

```powershell
cd service
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

### Başlatma

```powershell
cd service
$env:LIBRARY_DIR = "C:\Belgelerim"      # kitaba dönüşecek dosyaların klasörü (zorunlu)
$env:LIBRARY_AUTHOR = "Barış"           # kitapların yazarı (isteğe bağlı, varsayılan: Silverfish)
.\.venv\Scripts\python -m uvicorn --factory mclibrary.app:create_app --host 127.0.0.1 --port 8765
```

Servis yalnızca bu bilgisayardan erişilebilir (`127.0.0.1`). Ayakta olup olmadığını
tarayıcıda <http://127.0.0.1:8765/saglik> adresinden görebilirsiniz. Tüm uç noktaların
denenebileceği sayfa: <http://127.0.0.1:8765/docs>.

### Uç noktalar

| Uç nokta | Ne yapar |
|---|---|
| `GET /saglik` | `{"status": "ok", "library_dir": "...", "library_dir_exists": true}` |
| `POST /plan` | Henüz teslim edilmemiş ciltler ve atlanan dosyalar: `{"books": [{"id", "title", "author", "pages", "source"}], "skipped": [{"file", "reason"}]}` |
| `POST /onay` | Gövde: `{"ids": ["..."]}`. Sandığa konan ciltleri kaydeder. Yanıt: `{"accepted": n, "already_delivered": m}` |

- **Cilt id'si:** çıkarılan metnin SHA-256 özetinin ilk 16 karakteri, ardından `-` ve cilt
  numarası (`3f9a…c2-1`). Dosyanın adı değişirse aynı kitap tekrar gelmez; içeriği
  değişirse yeni kitap gelir.
- **Durum dosyası:** teslim edilen id'ler `LIBRARY_DIR\.mclibrary_state.json` dosyasında
  tutulur. Dosya önce geçici bir dosyaya yazılıp sonra yerine taşınır; yazma yarıda
  kesilirse eski hâli bozulmadan kalır. Silinirse bütün kitaplar yeniden teslim edilir.

### Testler

```powershell
cd service
.\.venv\Scripts\python -m pytest
```
