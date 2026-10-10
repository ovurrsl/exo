# Windows masaüstü kabul durumu — 10 Ekim 2026

Panel ve Settings düzeltmeleri ayrı **`work/windows-panel-controls`** dalında **`de85b2cf0d9a353425f7eb71b7971d8d1fed3f77`** olarak tutuldu, bağımsız incelemeden sonra **`f99234db`** ile `windows-native`'e birleştirildi ve fork'a gönderildi. Mac Swift/Metal/JACCL, Darwin dependency pin'leri, ortak protokol ve ürün API varsayılanı **52415** değiştirilmedi. Palet, font kuralları, ikon geometrisi ve 340 px panel genişliği korundu.

## Tamamlanan davranışlar

- Uzun hata ve API-kopyalama bildirimi aynı viewport bütçesinde kalır; mesaj alanı kayarken Settings/Quit görünür ve klavyeyle erişilebilir kalır.
- General, Model, Advanced ve Environment yalnız etkin sekmenin değişikliklerini kaydeder. Diğer sekmelerdeki taslaklar korunur; ilgisiz Environment hatası General kaydını engellemez. Değişiklik geri alındığında Save kapanır, About'ta Save bulunmaz.
- Çalışan/başlayan backend'de Save & Restart, durmuş backend'de Save ve sonraki başlatmayı anlatan metin görünür. Başarı bildirimi, response'tan doğrulanamayan bir restart gerçekleştiğini iddia etmez.
- Aynı ayarlar ve aynı etkin token isteği backend'de erken döner: dosya, startup kaydı ve token yazımı veya backend restart'ı yapılmaz. Token karşılaştırması saf unit testlerinde doğrulandı; gerçek Credential Manager hataları ayrıca kabul gerektirir.
- Bağımsız review'de bulunan token'ın doğrulamadan önce kırpılması düzeltildi. Ham kontrol karakterleri Rust doğrulamasına ulaşır; geçersiz token hatası kaybolmaz.

## Kanıt

| Kontrol                                                   | Sonuç                                                                                              |
| --------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Hedef UI regresyonları                                    | Önce beklenen RED, düzeltme sonrası GREEN                                                          |
| Açık/koyu tema Playwright                                 | Her temada 22 geçti, atlama yok; gerçek frozen state fixture'ı dahil                               |
| Vitest                                                    | 3 geçti                                                                                            |
| Svelte / TypeScript / Vite production build               | Svelte 0 hata/0 uyarı; diğerleri geçti                                                             |
| Rust desktop / probe-module / firewall-helper / lifecycle | Sırasıyla 21 / 10 / 4 / 3 geçti; settings alt grubu 7 geçti                                        |
| Rust Clippy ve formatter                                  | `-D warnings`, Cargo fmt ve değişen TS/Svelte Prettier geçti                                       |
| Python                                                    | 728 geçti, 8 atlandı, 190 slow dışlandı; tip ve Ruff kontrolü geçti                                |
| Bağımsız kod incelemesi                                   | Final immutable patch/commit eşliği doğrulandı; P2 kapandı, başka uygulanabilir gerileme bulunmadı |
| Gerçek Windows frozen controller probe                    | Running/Stopped unchanged save no-op; API hazır ve MlxCuda; explicit restart/stop graceful exit 0  |

Güncel birleşik **`f99234db`** kaynağı için hosted **[Windows checks](https://github.com/ovurrsl/exo/actions/runs/38061981735)** beş job'ın tamamında başarılı tamamlandı: desktop/UI, Windows CPU/Rust, Dashboard ve Windows/Darwin Python tip kontrolü. Aynı commit'in **[Darwin Nix build/flake check](https://github.com/ovurrsl/exo/actions/runs/38061981729/job/114241917205)** job'ı da geçti; iki Linux job'ı NVSHMEM/cuFile native bağımlılık hatalarıyla açık kaldı. Bu workflow'lar fiziksel GPU veya kurulum kabulü değildir.

Controller probe rastgele test portları ve izole namespace/veri dizini kullandı. Kullanıcı Credential Manager'ını veya startup kaydını okumadı/değiştirmedi; GUI, tepsi ve WebView oluşturmadı. Bu kanıt gerçek Settings penceresinin render kabulü değildir. Browser yoğunlukları 1 / 1,25 / 1,5 / 2 ve headless screenshot'lar fiziksel Windows DPI/monitör kabulü yerine geçmez.

Uygulayıcı kanıtları `worktrees/windows-panel-controls/build/acceptance/windows-panel-controls-20261010.md` ve aynı worktree'nin `build/panel-*` log/screenshot'larında; bağımsız review ana checkout `build/acceptance/windows-panel-controls-independent-review-20261010.md` dosyasındadır. Kanıtlar source repository'ye binary veya kişisel tam log olarak eklenmedi.

## Kurucu ve kalan kapılar

Güncel arayüz ve yeniden üretilmiş GPU runtime'ı bir araya getiren **imzasız review kurucusunun derlemesi tamamlandı**. GUI source commit'i `f99234db`, runtime source commit'i `7d11c690`, MLX `0.32.3.dev20261009+win.3`; sonraki production Python davranışı değişmedi. Microsoft fixed WebView2 `154.0.4258.62` ve 11.440 runtime dosyası hash kontrollerinden geçti.

Artefakt `app/windows/src-tauri/target/release/bundle/nsis/EXO Windows_0.3.70_x64-setup.exe`, **1.795.266.962 bayt / 1,67 GiB**. Son yazım 10 Ekim 2026 **18:26:30 +03:00**, SHA-256 **`975cc62d04053edf3d6724831039fca9f541821bae13d09b850926ef872f76c3`**; Authenticode sonucu `NotSigned`. Logdaki `Finished 1 bundle` sonucu ve taze dosya kimliği birlikte doğrulandı; eski 15:36 kurucusu bu kanıt değildir. Yeni paket henüz kurulmadı ve `release_ready=false` olarak tutulur.

Derleme logu `build/acceptance/windows-panel-controls-installer-build-20261010.log`; GUI/runtime/wheel/executable/build hash'lerini bağlayan yerel kayıt `build/acceptance/windows-panel-controls-installer-artifact-20261010.json`.

Bu kurucudaki runtime'ın [güncel tek-CUDA media kabulü](windows-runtime-media-acceptance-20261010.md) de geçti: iki Qwen3-VL görüntülü yanıt, FLUX üretim/düzenleme, iki iptal ve toparlanma, normal node/worker kapanışları. Bu, kurulum veya karma image pipeline kabulü değildir.

Kararlı sürüm kabulü açık: native Settings beş sekme/klavye/DPI/monitör, kurulum ve model koruyan kaldırma, geliştirme araçları olmayan temiz Windows'ta GPU üretimi, imzalı updater ve çalışan güvenlik taraması. [LAN raporu](windows-lan-acceptance-20261010.md) iki cihazlı ring/üretim/iptal/cache sonuçlarını ve daha büyük donanım/bellek sınırlarını ayrıca kaydeder.
