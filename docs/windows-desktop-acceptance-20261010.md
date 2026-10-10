# Windows masaüstü kabul durumu — 10 Ekim 2026

Güncel kaynak **`79de2150c1979663b63708c13dc6ddee5709f663`** fork'ın
`windows-native` dalına gönderildi. Mac panel davranışı konusu
**`aec96839e6072f28c3c858e1f0938661ac8b8657`** ve tanılama gizliliği konusu
**`79d8b9863281335188cb3282cc89370b843ace79`** ayrı commitlerle birleştirildi.
**Kararlı sürüm kabulü açık; `release_ready=false`.** Önceki
`f99234db` kabulü ve kurucu kimliği aşağıdaki tarihsel bölümde korunur.

## Güncel davranış ve kaynak doğrulaması

- GPU/sıcaklık/bellek ve görev ilerlemesi çekirdek panel satırında görünür. Model durumu Mac'teki öncelikle tek duruma indirgenir; Ready ile Running ayrıdır, başarısız görevler satır içinde görünür.
- Settings sekmeleri `aria-current` ile işaretlenir ve ok tuşlarıyla gezilir. Mac'in durum kapsülü geometrisi ve rengi izlenir; mevcut palet, ikonlar ve 340 px panel genişliği korunur.
- Native panel yalnız ana pencerenin ölçülmüş içerik yüksekliğini kullanır. Açılma/kapanma sonrası küçülme, üst workarea kenarı ve negatif koordinat hesabı kaynak/birim testlerinde doğrulandı. Gerçek mixed-DPI/monitör testi değildir.
- Tanılama ZIP'i yalnız `PRIVACY.txt`, `metadata.json`, `cluster-state.json` ve `network.txt` içerir. Ham backend/runner logları hiç okunmaz; generation istek parametreleri, serbest hata/evidence metinleri, JSON ortam değerleri ve yerel yollar çıkarılır. Bilinen kayıtlı credential ayrıca maskelenir. Cihaz/model kimlikleri ve ağ bilgileri kalabilir; dışa aktarma yereldir ve otomatik yükleme yapmaz.

Bu iki konu aralığında değişen dosyalar yalnız `app/windows/` altındadır.
Mac Swift/Metal/JACCL, Darwin pin'leri, ortak strict şemalar ve API varsayılanı
**52415** değişmedi. Bağımsız final panel incelemesinde bildirilen içerik yüksekliği,
çok runner durum metni ve üst workarea sabitlemesi bulguları kapandı; final
snapshot'ta başka uygulanabilir P1/P2 bulunmadı. Bu, bütün uygulamanın veya
fiziksel Windows görünümünün kapsamlı kabulü değildir.

| Kontrol     | Konu kaynağı / sonuç                                                                                    | Birleşik `79de2150` sonucu                                                                 |
| ----------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Playwright  | `aec96839`: light 27, dark 27; atlama yok                                                               | 27 geçti, atlama yok, 42,5 s                                                               |
| Vitest      | 3 dosyada 4 test geçti                                                                                  | 3 dosyada 4 test geçti                                                                     |
| Rust        | Derleme hedeflerinde 4 firewall + 10 frozen probe + 29 native/shared + 24 main + 3 lifecycle = 70 geçti | 4 + 10 + 32 + 27 + 3 = 76 geçti; 0 başarısız                                               |
| Tip / biçim | Svelte 0 hata/0 uyarı; TypeScript, Vite, strict Clippy, Cargo fmt ve değişen TS/Svelte Prettier geçti   | Svelte 0/0; TypeScript, strict Clippy ve Cargo fmt geçti                                   |
| Python      | 728 geçti, 8 atlandı, 190 slow dışlandı; tip 0/0/0, Ruff ve 323 dosyanın biçimi geçti                   | Bu batch üretim Python'unu değiştirmedi; masaüstü birleşik kontrolleri ayrıca çalıştırıldı |

Rust toplamları farklı derleme hedeflerinin test sayılarıdır; ortak modül
testlerinin birden çok hedefte çalışmasını benzersiz test sayısı olarak sunmaz.
Hedef UI gerilemeleri önce RED, düzeltmeden sonra GREEN görüldü. Birleşik
kaynağın son UI çalışması önceki panel fixture atlamasını da içermeden geçti.

Yerel kanıtlar ana checkout `exo/build/acceptance/` altında
`mac-design-integrated-ui-final-20261010.log`,
`mac-design-integrated-ui-unit-final-20261010.log`,
`mac-design-integrated-ui-check-20261010.log`,
`mac-design-integrated-rust-20261010.log` ve
`mac-design-integrated-clippy-20261010.log` dosyalarıdır. Konu logları
`worktrees/windows-panel-controls/build/design-*` altında; bağımsız final
rapor aynı worktree'de
`build/acceptance/windows-mac-design-independent-review-20261010.md`.

Güncel hosted sonuçları [Windows checks 38068184144](https://github.com/ovurrsl/exo/actions/runs/38068184144),
[38068180381](https://github.com/ovurrsl/exo/actions/runs/38068180381),
[CI 38068184261](https://github.com/ovurrsl/exo/actions/runs/38068184261) ve
[38068180571](https://github.com/ovurrsl/exo/actions/runs/38068180571) üzerinden
izlenir; bu rapor bunların tamamlandığı veya yeşil olduğu iddiasını taşımaz.
Tarihsel Windows/Darwin başarıları güncel commit'in hosted kabulü değildir.
Önceki Linux NVSHMEM/cuFile Nix bağımlılık hataları açık kalır.

## Native Settings ölçümünün kesin kapsamı

Tam **`aec96839e6072f28c3c858e1f0938661ac8b8657`** kaynağındaki izole yardımcı,
fixed WebView2 **`154.0.4258.62`** ile light/dark 10'ar örnek üretti.
Her iki rapor `passed=true`, exit 0 ve `eventLoopReturned=true` kaydetti.
Pencere gizli/odaksızdı, scale ve DPR 1'di; `get_settings` ve desktop snapshot
IPC'si birer kez çağrıldı. Backend başlamadı, gerçek ayarlar veya credentials
okunmadı/değişmedi. Çıkıştan sonraki sahip olunan yardımcı/browser profil
süreç kontrolünde her iki test için sıfır süreç kaldı.

| Tema  | Yerel probe kimliği                | Yardımcı binary SHA-256                                            |
| ----- | ---------------------------------- | ------------------------------------------------------------------ |
| Light | `153951be71c54b1aa9706797454768dd` | `4d90a65fe1ac82b5c8f2b5c0125a3c6483d5c224b1cd36036205d46cb7c74166` |
| Dark  | `f96c1ccf49a840ffbb54d5d1e7f5a7aa` | `14549cd3f4f456dd81c31e89bbca58ea58a9115161b7fa0f518f38a382ad5ffb` |

Raporlar
`worktrees/windows-panel-controls/build/acceptance/native-settings-probe-20261010/<kimlik>/report.json`
altında. İkisinde de gömülü CSS
`001bc7f817cf605343c9a41c3b9b47f616f25a3f8cda27080648f5efc0643074`,
JS `814b72f5f37f126edd9e1b36e44b76602d78f3ee8107eef0b72e2d87b2b1314a`.
Temaların binary hash'leri farklıdır; yalnız sourceCommit alanına dayanılmadı.

Bu salt okunur native DOM/IPC kanıtı **production Settings açıcı, paint,
beş sekmenin kullanıcı akışı, fiziksel DPI/monitör veya kurulum kabulü değildir**.
Önceki `0c5294ac` proof'ları ayrı kaynak ve asset hash'leriyle tarihsel tutulur;
bu yeni kaynakla birbirinin yerine kullanılamaz. Yeni ölçüm, sonraki
`79d8b986` ZIP değişikliğini içermez.

## Güvenlik ve verimlilik

Tamamlanan Codex Security diff taraması
**`b534fc0a-a4f4-410c-95ef-ac078d235fcb`** sabit
`931e0ff4a4fcdb0a5f04f7a71f3a5e4201867df3..0c5294acefbe1bf3d4811f2d120ef0ee3de1e602`
aralığına aittir: 187 değişen yol incelendi, 45 açık dışlama, 0 ertelenen.
Tek bulgu, manuel tanılama ZIP'inde canonical `input`/`instructions` ve
ham logların özel istemleri taşımasıydı; düşük önem/P3, yüksek güven, CWE-200.
Canonical rapor yerel
`C:/Users/ovurr/.codex/state/plugins/codex-security/scans/exo/0c5294acefbe1bf3d4811f2d120ef0ee3de1e602_20261010T155010Z_7mejhvjg/report.md`.

`79d8b986` bu dışa aktarma yolunu dört açık girdiye sınırladı; canonical ve
bilinmeyen/nested payload, serbest hata ve ZIP girdisi regresyonları birleşik
Rust kontrolünde geçti. **Düzeltme testleri yeni bir sealed güvenlik taraması
değildir.** Sonraki panel/ZIP değişiklikleri ve değişmemiş bütün upstream API
önceki tarama kapsamına eklenmiş sayılmaz.
[PR 2305/2306 düzeltmeleri](upstream-pr-review-20261010.md) ayrıca incelendi;
güncel main veya `7d11c690` frozen runtime bunları henüz içermez.

Salt okunur verimlilik raporu
`exo/build/acceptance/windows-efficiency-independent-review-20261010.md`,
Python `7d11c690` ve masaüstü `23a76e4a` kapsamına aittir. Bayt dönüşümündeki
%7,3741824 fazla raporlama, tarihsel exact-cache `prompt_tps` ve kısa istem KV
kopyaları açık bulgulardır. Önizleme aktarımı ve gizli pencere sorguları
ölçülmemiştir; hız kazancı iddia edilmez. [Gerçek LAN](windows-lan-acceptance-20261010.md)
ve [tek CUDA media](windows-runtime-media-acceptance-20261010.md) sonuçları
aynı `7d11c690` runtime kimliğiyle sınırlıdır.

## Güncel kurucu — final kanıt bekleniyor

**`79de2150` kaynağının kurucu derlemesi sürüyor.** Şu ana kadar 257 fixed
WebView2 dosyası ve 11.440 runtime dosyası doğrulandı; final `Finished 1 bundle`
ve yeni dosya SHA-256/boyut/yazım zamanı/Authenticode kimliği henüz kaydedilmedi.
Yerel log:
`exo/build/acceptance/windows-mac-design-installer-build-20261010.log`.

**Final artefakt kaydı: bekleniyor. Kurulum sonucu: bekleniyor.**
Derleme tamamlanınca yalnız taze dosyanın source/runtime/hash kimliği eklenebilir.
Aşağıdaki `975cc62d…` kurucusu eski `f99234db` GUI'ye aittir ve güncel kurucu
kanıtı değildir.

Açık kapılar: production native opener/paint, beş sekme/klavye,
fiziksel DPI/monitör, temiz araçsız Windows GPU kurulumu, model koruyan kaldırma,
imzalı updater, ikinci M1/üç fiziksel düğüm, karma vision/image ve VRAM üstü
LLM offload. Thunderbolt kullanıcının kararıyla ertelendi.

## f99234db dönemi — tarihsel kanıt

Aşağıdaki metin önceki snapshot'ın sonuçlarını ve artefakt kimliğini korur.
Buradaki “güncel” sözcüğü yalnız o snapshot'a aittir; güvenlik taramasının
beklediği ifadesi de o dönemin durumudur. Yukarıdaki tamamlanmış tarama ve yeni
panel sonuçları bu eski kurucunun fiziksel kabulünü genişletmez.
Panel ve Settings düzeltmeleri ayrı **`work/windows-panel-controls`** dalında **`de85b2cf0d9a353425f7eb71b7971d8d1fed3f77`** olarak tutuldu, bağımsız incelemeden sonra **`f99234db`** ile `windows-native`'e birleştirildi ve fork'a gönderildi. Mac Swift/Metal/JACCL, Darwin dependency pin'leri, ortak protokol ve ürün API varsayılanı **52415** değiştirilmedi. Palet, font kuralları, ikon geometrisi ve 340 px panel genişliği korundu.

### Tamamlanan davranışlar

- Uzun hata ve API-kopyalama bildirimi aynı viewport bütçesinde kalır; mesaj alanı kayarken Settings/Quit görünür ve klavyeyle erişilebilir kalır.
- General, Model, Advanced ve Environment yalnız etkin sekmenin değişikliklerini kaydeder. Diğer sekmelerdeki taslaklar korunur; ilgisiz Environment hatası General kaydını engellemez. Değişiklik geri alındığında Save kapanır, About'ta Save bulunmaz.
- Çalışan/başlayan backend'de Save & Restart, durmuş backend'de Save ve sonraki başlatmayı anlatan metin görünür. Başarı bildirimi, response'tan doğrulanamayan bir restart gerçekleştiğini iddia etmez.
- Aynı ayarlar ve aynı etkin token isteği backend'de erken döner: dosya, startup kaydı ve token yazımı veya backend restart'ı yapılmaz. Token karşılaştırması saf unit testlerinde doğrulandı; gerçek Credential Manager hataları ayrıca kabul gerektirir.
- Bağımsız review'de bulunan token'ın doğrulamadan önce kırpılması düzeltildi. Ham kontrol karakterleri Rust doğrulamasına ulaşır; geçersiz token hatası kaybolmaz.

### Kanıt

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

### Kurucu ve kalan kapılar

Güncel arayüz ve yeniden üretilmiş GPU runtime'ı bir araya getiren **imzasız review kurucusunun derlemesi tamamlandı**. GUI source commit'i `f99234db`, runtime source commit'i `7d11c690`, MLX `0.32.3.dev20261009+win.3`; sonraki production Python davranışı değişmedi. Microsoft fixed WebView2 `154.0.4258.62` ve 11.440 runtime dosyası hash kontrollerinden geçti.

Artefakt `app/windows/src-tauri/target/release/bundle/nsis/EXO Windows_0.3.70_x64-setup.exe`, **1.795.266.962 bayt / 1,67 GiB**. Son yazım 10 Ekim 2026 **18:26:30 +03:00**, SHA-256 **`975cc62d04053edf3d6724831039fca9f541821bae13d09b850926ef872f76c3`**; Authenticode sonucu `NotSigned`. Logdaki `Finished 1 bundle` sonucu ve taze dosya kimliği birlikte doğrulandı; eski 15:36 kurucusu bu kanıt değildir. Yeni paket henüz kurulmadı ve `release_ready=false` olarak tutulur.

Derleme logu `build/acceptance/windows-panel-controls-installer-build-20261010.log`; GUI/runtime/wheel/executable/build hash'lerini bağlayan yerel kayıt `build/acceptance/windows-panel-controls-installer-artifact-20261010.json`.

Bu kurucudaki runtime'ın [güncel tek-CUDA media kabulü](windows-runtime-media-acceptance-20261010.md) de geçti: iki Qwen3-VL görüntülü yanıt, FLUX üretim/düzenleme, iki iptal ve toparlanma, normal node/worker kapanışları. Bu, kurulum veya karma image pipeline kabulü değildir.

Kararlı sürüm kabulü açık: native Settings beş sekme/klavye/DPI/monitör, kurulum ve model koruyan kaldırma, geliştirme araçları olmayan temiz Windows'ta GPU üretimi, imzalı updater ve çalışan güvenlik taraması. [LAN raporu](windows-lan-acceptance-20261010.md) iki cihazlı ring/üretim/iptal/cache sonuçlarını ve daha büyük donanım/bellek sınırlarını ayrıca kaydeder.
