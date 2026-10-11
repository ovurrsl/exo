# EXO upstream dallarının incelemesi

10 Ekim 2026 tarihinde EXO upstream'de **280 dal** bulunuyor. Bu rapor,
Active sayfasının ilk listesinden daha geniş olarak mevcut bütün dalları kapsar.
Karşılaştırma tabanı, aynı tarihte upstream `main` ucundaki
`21a54c5ea0230a3bec1e1a786d200126c7e34ec6` commit'idir; Windows çalışmamızın
başlangıç tabanı da bu commit'tir.

Dalların adları, commit mesajları, ortak atadan değişen dosyaları ve gerektiğinde
kaynak farkları amaçlarını gösterir. Windows katkısı satırları bu proje için
değerlendirmedir; upstream dalının Windows üzerinde test edildiği anlamına gelmez.
Bu inceleme dallardaki kodları çalıştırmaz veya bütün kaynaklar için güvenlik
denetimi yapmaz. Hiçbir upstream dalı Windows dalımıza otomatik birleştirilmedi.

## Karşılaştırmayı okuma

- **İleri:** `main` atalarında bulunmayan dal commit'leri. Squash/rebase ile
  benzer bir değişiklik `main`e geçmiş olabilir; sayı tek başına yeni özellik sayısı değildir.
- **Geri:** Dalın atalarında bulunmayan `main` commit'leri. Büyük sayı entegrasyon
  ve protokol uyumu için daha fazla inceleme gerektirir.
- **Değişen dosya:** Ortak atadan dalın ucuna tree diff; `main` ile bütün farkın
  büyüklüğü veya test sayısı değildir.
- **PR:** Yalnız rapor tarihinde açık ve exact upstream repo/dal adına eşleşen
  PR'lar gösterilir. PR görünmemesi hiç PR açılmadığı veya kapatılmadığı demek değildir.
- SHA ve karşılaştırma linkleri snapshot'ı sabitler. Dal ve PR linklerinin
  içerikleri sonraki günlerde değişebilir; commit tarihleri committer tarihleridir.

## Windows ve NVIDIA için öncelik

1. **Küme ve süreç güvenilirliği:** `fix/pipeline-cancel-deadlock`,
   `fix/runner-stops-when-ring-aborts`, `fix/stalled-peer-blocks-cluster`,
   `fix/discovery-reconnect-after-stall` ve `fix/placement-counts-loading-instances`
   yaklaşımı sonraki karma küme hata matrisinde karşılaştırılmalı. Bazı dallar
   birbirini içerir; hepsini peş peşe cherry-pick etmek tekrar/conflict üretebilir.
2. **Model ve bellek:** `leo/add-gemma-4-parallelism`,
   `leo/handle-low-memory-situations`, `bump-required-mem` ve
   `alexcheema/robust-hf-config-parsing` Gemma/yerleştirme konularına temas eder.
   Yeni hesaplama ve model stratejileri precision, loading peak ve CUDA ile
   doğrulanmadan bizim dalda etkinleştirilmemeli.
3. **Namespace:** `fix/honour-namespace-env` aynı CLI sözleşmesi sorununa yönelir;
   Windows dalımızdaki düzeltmeyle karşılaştırılmalı, aynı değişiklik tekrar alınmamalı.
4. **NVIDIA dalları:** `cuda-build-improvement` Linux/Nix `libcuda.so` arama yolu
   çalışmasıdır. `leo/use-sm121-branch` ve `leo/dgx-spark-integrations` Linux
   işaretli vLLM/Transformers bağımlılıklarına dayanır; native Windows veya RTX 5070
   kabulü olarak gösterilemez. RTX 5070 wheel'imizin SM120 hedefiyle SM121 işi
   karıştırılmamalı.
5. **Mac özel kaynakları:** Thunderbolt bridge, ANE, RDMA/JACCL ve Swift değişiklikleri
   Windows uygulamamıza doğrudan taşınmaz. Mevcut M1 Air kümesi TCP ring kullanır.
6. **Büyük yeniden yazımlar:** Zenoh/Rust, snapshot/state schema ve Iroh dalları
   protokol/süreç mimarisini değiştirebilir. Mevcut fork release sözleşmesini koruma
   hedefi nedeniyle ayrı entegrasyon tasarımı gerektirir. `iroh` deneyinde networking
   dosyasının boşalması tamamlanmış bir taşıma olarak değerlendirilmemeli.

## Genel dağılım


| Dal grubu | Adet |
|---|---:|
| JakeHillion | 12 |
| Kök dallar | 59 |
| alexcheema | 32 |
| andrei | 12 |
| ciaran | 4 |
| codex | 19 |
| david | 10 |
| feat | 9 |
| fix | 70 |
| integ | 1 |
| leo | 42 |
| meta-instance-split | 1 |
| perf | 1 |
| releases | 3 |
| revert-1906-leo | 1 |
| sami | 4 |


69 dal main'den geri değildir. 2 dalın ucu main içinde bulunur (main dahil). Bu sayılar commit ancestry ölçüsüdür, yayın/kabul statüsü değildir.


## Bütün dallar


### 1. JakeHillion/images-formatted

Görsel üretimi ve düzenlemeyi runner, görev tipleri ve sohbet arayüzüne bağlar. Qwen-Image/Edit adaptörleri ile kısmi görsellerin akış halinde gösterilmesi de bu geniş dalda bulunur.

**Windows katkısı:** MLX ve görsel motoru tarafındaki çalışma M1 yolu için incelenebilir; RTX 5070 üzerinde yerel Windows çalıştırma desteği göstermiyor.

**Durum:** 206 ileri / 499 geri; 44 değişen dosya; son commit `9067033f`, 2026-01-09T16:15:51Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Support image editing in runner. Dosyalar: `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/lib/components/ChatMessages.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `pyproject.toml` ve 39 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9067033f203ab43e4ab4ba38c134ff5a542e3757) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9067033f203ab43e4ab4ba38c134ff5a542e3757) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/images-formatted).


### 2. JakeHillion/poulwnyystws

Baş commit mesajı Rust util paketindeki kullanılmayan tipleri, feature bayraklarını ve bağımlılıkları kaldırmayı anlatır. Ancak snapshot'ta ortak ataya göre net dosya farkı boş olduğundan uygulanabilir bağımsız bir yama olarak yorumlanmamalıdır.

**Windows katkısı:** Bakım temizliği niteliğindedir; Windows/CUDA veya M1 çalışma yoluna yeni bir motor eklemez.

**Durum:** 1 ileri / 293 geri; 0 değişen dosya; son commit `0bced30a`, 2026-02-10T20:31:53Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: util: remove dead code. Dosyalar: Bağımsız dosya değişikliği yok. [Sabit commit](https://github.com/exo-explore/exo/commit/0bced30a5745cc581f93ea6f3e54a378ecf1d40f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0bced30a5745cc581f93ea6f3e54a378ecf1d40f) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/poulwnyystws).


### 3. JakeHillion/qolrqmoxuotr

Model indirmelerinin Worker yerine Node seviyesinde yönetilmesini deneyen WIP düzenlemedir. Yeni download manager ve ana süreç bağlantıları ekler.

**Windows katkısı:** Düğüm düzeyindeki indirme mimarisi karma Windows–Mac kümesi için fikir verir; bitmiş bir Windows portu değildir.

**Durum:** 1 ileri / 477 geri; 4 değişen dosya; son commit `3e9c2961`, 2026-01-12T18:30:21Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: WIP: move downloads from Worker to Node. Dosyalar: `src/exo/download/__init__.py`, `src/exo/download/manager.py`, `src/exo/main.py`, `src/exo/worker/main.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/3e9c29618ed810822729183b5e7a1fb73a484cad) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3e9c29618ed810822729183b5e7a1fb73a484cad) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/qolrqmoxuotr).


### 4. JakeHillion/qotmmkpkktsv

Tek M3 Ultra benchmark tanımını yeniden adlandırır ve 2, 3, 4 düğümlü M3 Ultra ölçüm profilleri ekler. Değişiklik benchmark TOML dosyalarıyla sınırlıdır.

**Windows katkısı:** Çoklu Mac ölçümü için örnek olabilir; M1 veya RTX 5070 performansını doğrudan ölçmez.

**Durum:** 1 ileri / 201 geri; 5 değişen dosya; son commit `8dc859b8`, 2026-02-23T18:28:04Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: bench: add multi-node M3 Ultra benchmark specs for 2, 3, and 4 nodes. Dosyalar: `bench/1x-m3-ultra.toml`, `bench/2x-m3-ultra.toml`, `bench/3x-m3-ultra.toml`, `bench/4x-m3-ultra.toml`, `bench/bench.toml`. [Sabit commit](https://github.com/exo-explore/exo/commit/8dc859b8d2ba4000cbb67b1d2af103015cf80109) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8dc859b8d2ba4000cbb67b1d2af103015cf80109) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/qotmmkpkktsv).


### 5. JakeHillion/qqwursqotloo

uv2nix ile Python paketlemesini ve macOS DMG için PyInstaller paketini Nix akışına ekler. CI build ve typecheck düzeni de değişir.

**Windows katkısı:** Mac uygulamasını koruma açısından paketleme referansıdır; Windows installer veya CUDA motoru sunmaz.

**Durum:** 2 ileri / 462 geri; 6 değişen dosya; son commit `7acafe18`, 2026-01-19T10:40:13Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: nix: add PyInstaller package for macOS DMG. Dosyalar: `.github/actions/typecheck/action.yml`, `.github/workflows/build-app.yml`, `.github/workflows/pipeline.yml`, `flake.lock`, `flake.nix` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7acafe180ac7b1bc41fcae7c771b8c5fd6032b49) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7acafe180ac7b1bc41fcae7c771b8c5fd6032b49) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/qqwursqotloo).


### 6. JakeHillion/rwopytsxwtlp

Model kartlarına Git SHA sabitlemesi ekleyerek indirilen model revizyonlarını açık hale getirir. Çok sayıda görsel ve çıkarım kartıyla Renovate yapılandırması değişir.

**Windows katkısı:** İki platformda tekrarlanabilir model seçimi için yararlıdır; sabitlenen MLX modellerinin Windows/CUDA uyumluluğunu kanıtlamaz.

**Durum:** 1 ileri / 178 geri; 75 değişen dosya; son commit `bee33f78`, 2026-03-02T16:53:55Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: model_cards: add pinning by git sha. Dosyalar: `.github/renovate.json`, `resources/image_model_cards/exolabs--FLUX.1-Kontext-dev-4bit.toml`, `resources/image_model_cards/exolabs--FLUX.1-Kontext-dev-8bit.toml`, `resources/image_model_cards/exolabs--FLUX.1-Kontext-dev.toml`, `resources/image_model_cards/exolabs--FLUX.1-Krea-dev-4bit.toml` ve 70 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/bee33f78a0e6b10425b88be390ab8068402eea4b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...bee33f78a0e6b10425b88be390ab8068402eea4b) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/rwopytsxwtlp).


### 7. JakeHillion/syyqxzsolzox

Router içindeki get_node_id_keypair fonksiyonunda ulaşılamayan kodu kaldırır. Tek router dosyasına dokunan küçük bir temizliktir.

**Windows katkısı:** Ortak ağ kodunu sadeleştirir; Windows veya M1 için yeni işlev sağlamaz.

**Durum:** 1 ileri / 177 geri; 1 değişen dosya; son commit `75318b4d`, 2026-02-27T17:36:12Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: router: remove unreachable code in get_node_id_keypair. Dosyalar: `src/exo/routing/router.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/75318b4dc9df997bc0c930389b60156219b6d99b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...75318b4dc9df997bc0c930389b60156219b6d99b) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/syyqxzsolzox).


### 8. JakeHillion/torrents

Rust tabanlı torrent indirmelerini model dosyası filtreleme ve gömülü torrent varyantlarıyla bağlar. İlerleme, hız ve kalan süre hesaplamasını indirmeler ekranına taşır.

**Windows katkısı:** Her iki makinede model dağıtımı için mimari adaydır; rqbit/Rust paketlerinin yerel Windows build'i ayrıca doğrulanmalıdır.

**Durum:** 6 ileri / 479 geri; 76 değişen dosya; son commit `563e94ab`, 2026-01-12T15:12:56Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat(downloads): add ETA and speed tracking for torrent downloads. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/routes/downloads/+page.svelte`, `rust/downloads/Cargo.toml`, `rust/downloads/src/bencode.rs` ve 71 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/563e94ab6c177a3b108f596cb03e85e5aa03c5fa) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...563e94ab6c177a3b108f596cb03e85e5aa03c5fa) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/torrents).


### 9. JakeHillion/vmwnonkzsnuo

mlx-lm bağımlılığını günceller. Değişiklik Python bağımlılık manifesti ve kilit dosyasıyla sınırlıdır.

**Windows katkısı:** M1'in MLX yolunu etkileyebilir; tek başına RTX 5070 için CUDA veya Windows desteği oluşturmaz.

**Durum:** 1 ileri / 330 geri; 2 değişen dosya; son commit `0806c92a`, 2026-02-05T16:34:41Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: deps: update mlx-lm. Dosyalar: `pyproject.toml`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/0806c92ac9b8ab7fae2757446894621ce1f63bfd) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0806c92ac9b8ab7fae2757446894621ce1f63bfd) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/vmwnonkzsnuo).


### 10. JakeHillion/vnwuyypxwqqs

MLX'in gecikmeli import davranışını test eden NOCOMMIT denemesidir. Nix MLX kaynağını JakeHillion fork revizyonuna çevirir ve bağımlılık kilitlerini günceller.

**Windows katkısı:** Import sorunlarını incelemek için tarihsel deneydir; hazır Windows çözümü sayılmamalı ve M1 bağımlılıkları körlemesine değiştirilmemelidir.

**Durum:** 1 ileri / 232 geri; 3 değişen dosya; son commit `e9bd90a6`, 2026-02-20T11:40:41Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: NOCOMMIT: test mlx lazy import. Dosyalar: `nix/mlx.nix`, `pyproject.toml`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/e9bd90a647dc29edaf5b34be91cdba94a0eca4c5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e9bd90a647dc29edaf5b34be91cdba94a0eca4c5) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/vnwuyypxwqqs).


### 11. JakeHillion/wnpzkupouslp

Ağ kopmalarına birden fazla başarısız ping toleransı ekler ve indirme koordinatörü olaylarını worker kanalından geçirir. Olay düşürme testleri ile düşürülen olayların loglarını da içerir.

**Windows katkısı:** Karma kümenin geçici bağlantı kayıplarına dayanıklılığı için ilgilidir; Windows GPU backend'ini çözmez.

**Durum:** 4 ileri / 235 geri; 6 değişen dosya; son commit `0424fb57`, 2026-02-20T12:35:01Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: add logging for dropping events. Dosyalar: `rust/networking/src/discovery.rs`, `src/exo/download/coordinator.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_partition_recovery.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/0424fb57bd4ecc9b4cda5c78b038101589f25f90) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0424fb57bd4ecc9b4cda5c78b038101589f25f90) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/wnpzkupouslp).


### 12. JakeHillion/yvqrzonuknxu

Nix içinde uv2nix tabanlı Python paketleme düzeni kurar. Pipeline, flake ve Python paket parçaları değişir.

**Windows katkısı:** Mac/Linux geliştirme paketlemesine yöneliktir; yerel Windows kurulum yolu göstermez.

**Durum:** 1 ileri / 462 geri; 5 değişen dosya; son commit `ab684061`, 2026-01-19T10:40:13Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: nix: add Python packaging with uv2nix. Dosyalar: `.github/actions/typecheck/action.yml`, `.github/workflows/pipeline.yml`, `flake.lock`, `flake.nix`, `python/parts.nix`. [Sabit commit](https://github.com/exo-explore/exo/commit/ab684061c8ab13efb18583b6bdf266cc4f7d2d25) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ab684061c8ab13efb18583b6bdf266cc4f7d2d25) · [Dal](https://github.com/exo-explore/exo/tree/JakeHillion/yvqrzonuknxu).


### 13. add-glm5-support

GLM-5 için farklı nicemleme seçeneklerine ait model kartları ve MLX yükleme desteği ekler. Model kartı işleme ile utils_mlx kodu değişir.

**Windows katkısı:** M1 model kataloğu için referanstır; GLM-5 kartı eklemek RTX 5070'de yerel Windows motoru sağlamak anlamına gelmez.

**Durum:** 1 ileri / 262 geri; 6 değişen dosya; son commit `21b594b1`, 2026-02-17T10:20:34-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: add GLM-5 model support. Dosyalar: `resources/inference_model_cards/mlx-community--GLM-5-4bit.toml`, `resources/inference_model_cards/mlx-community--GLM-5-8bit-MXFP8.toml`, `resources/inference_model_cards/mlx-community--GLM-5-MXFP4-Q8.toml`, `resources/inference_model_cards/mlx-community--GLM-5.toml`, `src/exo/shared/models/model_cards.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/21b594b1764e2f7b98076fbb4531dda26193c25e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...21b594b1764e2f7b98076fbb4531dda26193c25e) · [Dal](https://github.com/exo-explore/exo/tree/add-glm5-support).


### 14. ai-slop

Runner alt süreçlerini JSON argümanları ve dosya tanıtıcılarına dayalı kanallarla başlatacak şekilde yeniden düzenler. PyInstaller gibi frozen uygulamalara --exo-runner giriş yolu da ekler.

**Windows katkısı:** pass_fds ve FD mirası Windows portunda ayrıca ele alınması gereken platform bağımlılıklarıdır; Mac runner davranışı da korunarak taşınmalıdır.

**Durum:** 1 ileri / 173 geri; 9 değişen dosya; son commit `16a3ab51`, 2026-03-03T10:49:36Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: sloppin it up. Dosyalar: `src/exo/__main__.py`, `src/exo/shared/types/worker/runner_args.py`, `src/exo/utils/fd_channels.py`, `src/exo/worker/main.py`, `src/exo/worker/runner/bootstrap.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/16a3ab51551756c825f6cde807b88aaf035aeec8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...16a3ab51551756c825f6cde807b88aaf035aeec8) · [Dal](https://github.com/exo-explore/exo/tree/ai-slop).


### 15. aiohttp

Adının tersine indirme HTTP istemcisini aiohttp'tan httpx.AsyncClient'a taşır. Yanıt alanları, streaming, timeout ve backoff kodu buna göre düzenlenir.

**Windows katkısı:** Ortak indirme katmanı için değerlendirilebilir; bu HTTP göçü yerel Windows CUDA çalışmasını kanıtlamaz.

**Durum:** 1 ileri / 253 geri; 5 değişen dosya; son commit `523eff54`, 2026-02-18T16:57:07Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: aaa. Dosyalar: `pyproject.toml`, `src/exo/download/download_utils.py`, `src/exo/download/impl_shard_downloader.py`, `src/exo/utils/keyed_backoff.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/523eff541eeae04d4de74338879ce9070d97b4b3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...523eff541eeae04d4de74338879ce9070d97b4b3) · [Dal](https://github.com/exo-explore/exo/tree/aiohttp).


### 16. alexcheema/add-qwen3-coder-next

Qwen3-Coder-Next'in 4/5/6/8 bit ve bf16 model kartlarını ekler. Dal ayrıca bir main birleştirme commit'i içerir.

**Windows katkısı:** M1 model seçimiyle ilgilidir; MLX kartları RTX 5070 için ayrı bir Windows motoru değildir.

**Durum:** 2 ileri / 334 geri; 5 değişen dosya; son commit `9e81b34b`, 2026-02-05T05:41:53-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into alexcheema/add-qwen3-coder-next. Dosyalar: `resources/inference_model_cards/mlx-community--Qwen3-Coder-Next-4bit.toml`, `resources/inference_model_cards/mlx-community--Qwen3-Coder-Next-5bit.toml`, `resources/inference_model_cards/mlx-community--Qwen3-Coder-Next-6bit.toml`, `resources/inference_model_cards/mlx-community--Qwen3-Coder-Next-8bit.toml`, `resources/inference_model_cards/mlx-community--Qwen3-Coder-Next-bf16.toml`. [Sabit commit](https://github.com/exo-explore/exo/commit/9e81b34bc54f3ea08f75541464cb071bbb062cc3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9e81b34bc54f3ea08f75541464cb071bbb062cc3) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/add-qwen3-coder-next).


### 17. alexcheema/add-step-3.5-flash

Step 3.5 Flash model kartları ve MLX tensor parallel desteği ekler. g_proj ve MoE shard düzenini düzeltirken runner/API iptal çalışmasını da birleştirir.

**Windows katkısı:** Mac çıkarım doğruluğu için önemlidir; yerel Windows/CUDA ve karma motor shard uyumu ayrıca gerekir.

**Durum:** 7 ileri / 330 geri; 22 değişen dosya; son commit `cbe68543`, 2026-02-05T12:06:50-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: match mlx-lm Step3p5 MoE sharding exactly to fix gibberish output. Dosyalar: `MISSED_THINGS.md`, `resources/inference_model_cards/mlx-community--Step-3.5-Flash-4bit.toml`, `resources/inference_model_cards/mlx-community--Step-3.5-Flash-6bit.toml`, `resources/inference_model_cards/mlx-community--Step-3.5-Flash-8Bit.toml`, `src/exo/master/adapters/chat_completions.py` ve 17 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/cbe6854359a5d527c5cd39c703e6e0ff2ffbc1fc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...cbe6854359a5d527c5cd39c703e6e0ff2ffbc1fc) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/add-step-3.5-flash).


### 18. alexcheema/ane-profiling-dashboard

GPU ve yönlü bağlantı profillemesinin üzerine Apple Neural Engine güç ve hesaplama ölçümleri ekler. Hassasiyet, nicemleme ve eşzamanlılık taramalarını dashboard ve düğüm metriklerine bağlar.

**Windows katkısı:** M1'de ANE ölçümü açısından ilgilidir; ANE profilinin varlığı RTX 5070 desteği veya ANE üzerinden model çıkarımı kanıtı değildir.

**Durum:** 17 ileri / 34 geri; 30 değişen dosya; son commit `1a08f699`, 2026-05-03T20:00:11+01:00. Açık PR: [#2041](https://github.com/exo-explore/exo/pull/2041).

**Kanıt:** Son commit: fix(profilers): sweep ANE compute concurrency. Dosyalar: `dashboard/src/lib/components/GpuRichBar.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte`, `dashboard/src/lib/components/index.ts`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/connection-type.ts` ve 25 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/1a08f699bb6e850ebb122d159d3d0fa335c2eed8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1a08f699bb6e850ebb122d159d3d0fa335c2eed8) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/ane-profiling-dashboard).


### 19. alexcheema/continuous-batching

MLX çıkarımında istekleri sürekli batch'e katma akışı kurar. Ertelenmiş prefill, istek başına sampling/parser, tool çağrıları, serileştirme darboğazları ve silinen instance runner temizliği üzerinde düzeltmeler içerir.

**Windows katkısı:** M1 tarafındaki throughput ve görev yaşam döngüsü için değerlidir; Windows/CUDA motorunda aynı batching sözleşmesi ayrıca uygulanmalıdır.

**Durum:** 17 ileri / 279 geri; 18 değişen dosya; son commit `7469f44e`, 2026-02-15T18:41:22-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: clean up stale runners from state when instance is deleted. Dosyalar: `.mlx_typings/mlx_lm/generate.pyi`, `.mlx_typings/mlx_lm/tokenizer_utils.pyi`, `AGENTS.md`, `conftest.py`, `src/exo/shared/apply.py` ve 13 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7469f44e58afe6f49f827da5240702908915eb9c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7469f44e58afe6f49f827da5240702908915eb9c) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/continuous-batching).


### 20. alexcheema/dashboard-stop-button

Sohbet ekranına üretimi durdurma düğmesi ekler ve API/runner iptal akışını bağlar. Sonraki commit'ler main ve cancellation birleşmelerindeki sorunları düzeltir.

**Windows katkısı:** Windows–Mac istemci deneyimine ortak katkı sağlayabilir; GPU çalışma platformunu değiştirmez.

**Durum:** 11 ileri / 279 geri; 18 değişen dosya; son commit `c7b7523b`, 2026-02-13T10:13:51-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Fix merge conflicts and post-merge issues. Dosyalar: `MISSED_THINGS.md`, `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `pyproject.toml`, `src/exo/master/adapters/chat_completions.py` ve 13 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/c7b7523bb4d6d41667ba5f20e347c38411745eb3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c7b7523bb4d6d41667ba5f20e347c38411745eb3) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/dashboard-stop-button).


### 21. alexcheema/debug-state-catchup-race

State catch-up sırasında erken gelen olayların kaybolmasını önlemeye çalışır. NodeGatheredInfo olaylarının API ve worker akışına teşhis logları ekler.

**Windows katkısı:** Karma kümede ilk bağlantı ve state tutarlılığı için ilgilidir; Windows backend desteği değildir.

**Durum:** 2 ileri / 386 geri; 2 değişen dosya; son commit `922e8075`, 2026-01-23T16:03:22-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: debug: add logging for NodeGatheredInfo event flow. Dosyalar: `src/exo/master/api.py`, `src/exo/worker/main.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/922e8075d31187684b464e07457612904dfea680) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...922e8075d31187684b464e07457612904dfea680) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/debug-state-catchup-race).


### 22. alexcheema/event-index-liveness

Düğüm canlılığını zaman damgaları yerine olay indeksi eskimesiyle izlemeye geçirir. Master, worker, state uygulaması ve testlerde buna uygun değişiklikler yapar.

**Windows katkısı:** Farklı makinelerin saatlerinden bağımsız canlılık takibi için yararlıdır; RTX 5070 çıkarım desteğine doğrudan katkısı yoktur.

**Durum:** 3 ileri / 279 geri; 6 değişen dosya; son commit `ad60cf09`, 2026-02-13T10:09:53-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into alexcheema/event-index-liveness. Dosyalar: `src/exo/master/main.py`, `src/exo/master/tests/test_master.py`, `src/exo/shared/apply.py`, `src/exo/shared/types/events.py`, `src/exo/shared/types/state.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ad60cf09fa9ee1692a0a18ad8d511e38722f5aa2) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ad60cf09fa9ee1692a0a18ad8d511e38722f5aa2) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/event-index-liveness).


### 23. alexcheema/event-sourcing-snapshots

Olay kaynaklı state akışını temizler ve snapshot üzerinden catch-up ekler. API, worker ve router taraflarında yeni state alma yolunu düzenler.

**Windows katkısı:** Windows–Mac kümesine yeniden katılım ve uzun olay geçmişi maliyeti açısından değerlidir; hesaplama motorlarını eşitlemez.

**Durum:** 1 ileri / 36 geri; 26 değişen dosya; son commit `c40f56db`, 2026-05-01T02:10:19+01:00. Açık PR: [#2011](https://github.com/exo-explore/exo/pull/2011) (taslak).

**Kanıt:** Son commit: event-sourcing cleanup + snapshot-based catch-up. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_master.py` ve 21 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/c40f56db5f9f8b6b68ceaacbd0eb8494532e3575) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c40f56db5f9f8b6b68ceaacbd0eb8494532e3575) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/event-sourcing-snapshots).


### 24. alexcheema/external-model-paths

Hugging Face Hub cache'i ve özel klasörlerden yerel modelleri otomatik keşfetme desteği ekler. Daha geniş dal model yükleme ilerlemesi, onboarding, ayarlar ve gerçek topoloji gösterimini de içerir.

**Windows katkısı:** Mevcut Windows/Mac model dosyalarını yeniden kullanma amacıyla ilgilidir; keşfedilen her formatın RTX 5070 veya MLX tarafından yürütülebileceğini kanıtlamaz.

**Durum:** 70 ileri / 216 geri; 33 değişen dosya; son commit `6a1f6d73`, 2026-02-23T09:56:02-08:00. Açık PR: [#1598](https://github.com/exo-explore/exo/pull/1598) (taslak).

**Kanıt:** Son commit: feat: auto-discover models from HuggingFace Hub cache and custom paths. Dosyalar: `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/EXOApp.swift`, `app/EXO/EXO/ExoProcessController.swift`, `app/EXO/EXO/Views/FirstLaunchPopout.swift`, `app/EXO/EXO/Views/SettingsView.swift` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6a1f6d734ab15c9d986b07750c3b0b14d9859286) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6a1f6d734ab15c9d986b07750c3b0b14d9859286) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/external-model-paths).


### 25. alexcheema/fix-download-resume-buttons

İndirmeler sayfasında düğme ikonlarını, imleç davranışını ve metin kontrastını iyileştirir. Commit'lerde geçici ekran görüntüleri ile main birleştirmeleri de vardır.

**Windows katkısı:** Ortak dashboard kullanılabilirliği için küçük katkıdır; yerel Windows veya M1 motoruna etki etmez.

**Durum:** 9 ileri / 202 geri; 1 değişen dosya; son commit `9b0d4cf1`, 2026-02-23T10:27:46-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: improve text contrast on downloads page. Dosyalar: `dashboard/src/routes/downloads/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/9b0d4cf10b85bd1ccbadaaf774f6bb3cbccef704) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9b0d4cf10b85bd1ccbadaaf774f6bb3cbccef704) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/fix-download-resume-buttons).


### 26. alexcheema/fix-instance-preparing-delay

Yerel model başlatılırken hazırlık durumunun ele alınışını düzeltir. macmon fallback'i, Nix/PyInstaller paketlemesi ve kurulum belgeleri de bu dalda değişir.

**Windows katkısı:** M1'de yerel model yükleme ve metrik toplama için ilgilidir; Windows'ta macmon yerine uygun platform yolu gerekir.

**Durum:** 3 ileri / 137 geri; 9 değişen dosya; son commit `781428a1`, 2026-03-24T16:54:01-07:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Fix local model launch preparation handling. Dosyalar: `CONTRIBUTING.md`, `README.md`, `flake.nix`, `packaging/pyinstaller/exo.spec`, `src/exo/download/coordinator.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/781428a17671415d71b0af51b73acb3fdcfa0fcb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...781428a17671415d71b0af51b73acb3fdcfa0fcb) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/fix-instance-preparing-delay).


### 27. alexcheema/fix-local-network-permission-reboot

macOS uygulamasının entitlements bilgisini koruyup --deep codesign kullanımını kaldırarak yeniden başlatma sonrası yerel ağ izni sorununu hedefler. Sparkle'ın iç içe binary'lerini doğru sırada imzalar.

**Windows katkısı:** M1 uygulama paketini korumak için doğrudan ilgilidir; Windows ağ izinleri veya CUDA ile ilgili değildir.

**Durum:** 2 ileri / 164 geri; 3 değişen dosya; son commit `ed3a974c`, 2026-03-06T01:48:15-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: sign all Sparkle framework nested binaries inside-out. Dosyalar: `.github/workflows/build-app.yml`, `app/EXO/EXO/EXO.entitlements`, `packaging/entitlements/runtime.entitlements`. [Sabit commit](https://github.com/exo-explore/exo/commit/ed3a974c61308e9d83ffcb60524bf5e3aaa84044) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ed3a974c61308e9d83ffcb60524bf5e3aaa84044) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/fix-local-network-permission-reboot).


### 28. alexcheema/fix-stuck-download-after-cancel

İptalden sonra indirme durumunun kalıcı olarak takılı kalmasını düzeltir. Koordinatör, state uygulaması ve indirme durum testleri değişir.

**Windows katkısı:** Her iki düğümün ortak indirme akışında incelenebilir; Windows GPU çalıştırma desteği eklemez.

**Durum:** 1 ileri / 191 geri; 4 değişen dosya; son commit `73599fba`, 2026-02-24T11:13:55-08:00. Açık PR: [#1614](https://github.com/exo-explore/exo/pull/1614) (taslak).

**Kanıt:** Son commit: fix: download gets permanently stuck after cancellation. Dosyalar: `src/exo/download/coordinator.py`, `src/exo/shared/apply.py`, `src/exo/shared/tests/conftest.py`, `src/exo/shared/tests/test_apply/test_apply_node_download.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/73599fbaecc34a6ee02b91594616848d3e0b7917) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...73599fbaecc34a6ee02b91594616848d3e0b7917) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/fix-stuck-download-after-cancel).


### 29. alexcheema/graceful-loading-shutdown

Shutdown zaman aşımında runner'ın zorla sonlandırılmasını sağlar. Ayrıca dağıtık başlatma betiğinin pytest test olarak toplanmasını engeller.

**Windows katkısı:** Karma kümede takılmış yüklemelerin temizliği için ilgilidir; Windows alt süreç sonlandırma semantiği ayrıca doğrulanmalıdır.

**Durum:** 2 ileri / 272 geri; 2 değişen dosya; son commit `e70c7e73`, 2026-02-16T11:12:20-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Exclude start_distributed_test.py from pytest collection. Dosyalar: `pyproject.toml`, `src/exo/worker/main.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/e70c7e73d22383fbb923e3cd6e23c1b044900824) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e70c7e73d22383fbb923e3cd6e23c1b044900824) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/graceful-loading-shutdown).


### 30. alexcheema/meta-instance

İstenen model instance durumunu tanımlayan MetaInstance katmanı ve reconciliation süreç yöneticileri ekler. Instance sağlığı, düğüm zaman aşımı ve dashboard/API akışı bu deklaratif yaşam döngüsüne bağlanır.

**Windows katkısı:** Windows–Mac kümesinin otomatik toparlanması için mimari adaydır; motor ve taşıma uyumluluğunu kendi başına sağlamaz.

**Durum:** 1 ileri / 216 geri; 23 değişen dosya; son commit `928c41b1`, 2026-02-21T13:05:10-08:00. Açık PR: [#1519](https://github.com/exo-explore/exo/pull/1519).

**Kanıt:** Son commit: feat: add MetaInstance declarative layer with reconciliation. Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `src/exo/master/api.py`, `src/exo/master/main.py`, `src/exo/master/process_managers/__init__.py` ve 18 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/928c41b13c128e8f7522c82ad6fac0cb1940175b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...928c41b13c128e8f7522c82ad6fac0cb1940175b) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/meta-instance).


### 31. alexcheema/mlx-distributed-transfer

Model metadata ve ağırlıklarını düğümler arasında MLX üzerinden aktarır. Katman katman broadcast, shard öncesi ağırlıkların bırakılması ve Step35 yükleme düzeltmeleriyle tepe bellek tüketimini azaltmayı hedefler.

**Windows katkısı:** Mac düğümleri için doğrudan ilgilidir; MLX ağırlık broadcast'ini yerel Windows/CUDA düğümüne uyarlamak ayrı iştir.

**Durum:** 20 ileri / 262 geri; 13 değişen dosya; son commit `de5c1212`, 2026-02-17T10:05:43-08:00. Açık PR: [#1463](https://github.com/exo-explore/exo/pull/1463) (taslak).

**Kanıt:** Son commit: fix: add missing tasks arg to get_transition_events(). Dosyalar: `AGENTS.md`, `src/exo/master/api.py`, `src/exo/master/main.py`, `src/exo/shared/types/api.py`, `src/exo/shared/types/commands.py` ve 8 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/de5c1212eec985aeedc47f75948b0f2efd7ce873) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...de5c1212eec985aeedc47f75948b0f2efd7ce873) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/mlx-distributed-transfer).


### 32. alexcheema/model-picker-downloaded-filter

Model seçicide indirme uygunluğunu gösterir ve Downloaded filtresi ekler. Değişiklik dashboard bileşenleri ve indirme yardımcı kodundadır.

**Windows katkısı:** Windows–Mac model seçiminde kullanışlı UI katkısıdır; çalışma motorunu veya model formatı uyumluluğunu değiştirmez.

**Durum:** 3 ileri / 334 geri; 6 değişen dosya; son commit `0afc779a`, 2026-02-05T05:39:34-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into alexcheema/model-picker-downloaded-filter. Dosyalar: `dashboard/src/lib/components/HuggingFaceResultItem.svelte`, `dashboard/src/lib/components/ModelFilterPopover.svelte`, `dashboard/src/lib/components/ModelPickerGroup.svelte`, `dashboard/src/lib/components/ModelPickerModal.svelte`, `dashboard/src/lib/utils/downloads.ts` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/0afc779a0d9542b23299617a7b1acd46efafac28) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0afc779a0d9542b23299617a7b1acd46efafac28) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/model-picker-downloaded-filter).


### 33. alexcheema/model-selection-ux

Model seçimi, ilk açılış, uygulama ayarları ve yükleme geri bildirimi üzerinde geniş bir UX düzenlemesidir. Swift uygulama ekranları ile Svelte dashboard dosyaları birlikte değişir.

**Windows katkısı:** Dashboard kısmı ortak kullanılabilir, Swift uygulama kısmı M1 için ilgilidir; yerel Windows hesaplama desteği eklemez.

**Durum:** 26 ileri / 227 geri; 28 değişen dosya; son commit `cd9f62d3`, 2026-02-20T13:14:49Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge branch 'main' into alexcheema/model-selection-ux. Dosyalar: `.github/workflows/build-app.yml`, `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/EXOApp.swift`, `app/EXO/EXO/ExoProcessController.swift`, `app/EXO/EXO/Views/FirstLaunchPopout.swift` ve 23 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/cd9f62d37bc5fd0d33a2538c0c39b46230beeeab) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...cd9f62d37bc5fd0d33a2538c0c39b46230beeeab) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/model-selection-ux).


### 34. alexcheema/mtp-speculative-decoding

DeepSeek V3 için Multi-Token Prediction modülü ve speculative decode akışı ekler. Birim testleri ve CI'da Metal kernel bulunmadığında entegrasyon testini atlama düzeni de vardır.

**Windows katkısı:** MLX/Metal yolu M1 için incelenebilir; RTX 5070'de yerel Windows MTP yürütmesini göstermiyor.

**Durum:** 7 ileri / 279 geri; 10 değişen dosya; son commit `229b21fa`, 2026-02-13T09:41:08-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: skip MTP integration test when Metal kernel unavailable on CI. Dosyalar: `src/exo/worker/engines/mlx/constants.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/engines/mlx/mtp/__init__.py`, `src/exo/worker/engines/mlx/mtp/module.py`, `src/exo/worker/engines/mlx/mtp/speculative_decode.py` ve 5 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/229b21fa8c021f70d6c2ac93d6bcf161df666e12) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...229b21fa8c021f70d6c2ac93d6bcf161df666e12) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/mtp-speculative-decoding).


### 35. alexcheema/no-silent-instance-override

Commit geçmişi tek düğümlü placement'ta instance_meta değerinin sessizce değiştirilmesini kaldırmayı amaçlar. Snapshot'ta ortak ataya göre net dosya farkı boş olduğundan bu dalı bağımsız uygulanabilir düzeltme diye sunmak doğru olmaz.

**Windows katkısı:** Placement niyeti açısından tarihsel referanstır; yeni Windows veya M1 işlevinin net yaması görünmüyor.

**Durum:** 2 ileri / 200 geri; 0 değişen dosya; son commit `92f9cd48`, 2026-02-23T10:46:18-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge branch 'main' into alexcheema/no-silent-instance-override. Dosyalar: Bağımsız dosya değişikliği yok. [Sabit commit](https://github.com/exo-explore/exo/commit/92f9cd4820b10b6ac5013b35d62d06fcf9eceab8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...92f9cd4820b10b6ac5013b35d62d06fcf9eceab8) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/no-silent-instance-override).


### 36. alexcheema/omlx-feel-ui

oMLX tarzı dashboard ve uygulama görünümüyle küme/model/indirme akışını yeniden düzenler. Son commit'lerde gerçek recent-request istatistikleri ve API'nin olay günlüğünü tekrar taramaması için cache eklenir.

**Windows katkısı:** Ortak dashboard ve Mac uygulama kullanımına katkıdır; oMLX benzeri görünüm Windows CUDA motoru anlamına gelmez.

**Durum:** 16 ileri / 45 geri; 33 değişen dosya; son commit `84e40e52`, 2026-04-25T23:13:41+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: perf(api): cache recent text-gen state instead of walking event log. Dosyalar: `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/EXOApp.swift`, `app/EXO/EXO/Services/ServerStatsService.swift`, `dashboard/src/app.css`, `dashboard/src/app.html` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/84e40e524c2fddd5fa55f7698b4710e1794cdc7a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...84e40e524c2fddd5fa55f7698b4710e1794cdc7a) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/omlx-feel-ui).


### 37. alexcheema/profilers-dashboard

GPU ve yönlü ağ bağlantısı profillemesini topoloji ekranına bağlar. RTT, jitter, bant genişliği, RDMA probe ve bağlantı türünün kararlı gösterimi üzerinde düzeltmeler içerir.

**Windows katkısı:** Karma kümenin darboğazlarını anlamak için yararlıdır; MLX GPU profiler'ın RTX 5070/Windows üzerinde çalıştığı varsayılamaz.

**Durum:** 13 ileri / 34 geri; 23 değişen dosya; son commit `d1f4b24d`, 2026-05-03T17:49:41+01:00. Açık PR: [#2010](https://github.com/exo-explore/exo/pull/2010).

**Kanıt:** Son commit: fix(profilers): use local RDMA interfaces in probe matrix. Dosyalar: `dashboard/src/lib/components/GpuRichBar.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte`, `dashboard/src/lib/components/index.ts`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/connection-type.ts` ve 18 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/d1f4b24d5e660af8467e24d5109c6e487b3b7cf6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...d1f4b24d5e660af8467e24d5109c6e487b3b7cf6) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/profilers-dashboard).


### 38. alexcheema/rdma-health-detection

MetaInstance ve dağıtık yükleme çalışmalarını içeren geniş bir küme sağlığı dalıdır. RDMA uyarısını doğrudan Thunderbolt bağlı çiftlerle sınırlayıp eski peer'leri ve zaman aşımındaki runner'ları temizler.

**Windows katkısı:** Mac bağlantı sağlığını koruma için ilgilidir; RTX 5070'li Windows makinede RDMA varlığını veya desteğini kanıtlamaz.

**Durum:** 47 ileri / 261 geri; 31 değişen dosya; son commit `d923f776`, 2026-02-17T10:49:43-08:00. Açık PR: [#1484](https://github.com/exo-explore/exo/pull/1484).

**Kanıt:** Son commit: chore: retrigger CI. Dosyalar: `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `src/exo/main.py` ve 26 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/d923f77629860a7720cf939f5b083a174202731c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...d923f77629860a7720cf939f5b083a174202731c) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/rdma-health-detection).


### 39. alexcheema/reliable-mdns-discovery

Darwin mDNS duyuru/keşif akışını daha güvenilir hale getirir. GPU/bağlantı profillemesi ve dashboard topoloji iyileştirmeleri de aynı dalın geçmişinde bulunur.

**Windows katkısı:** M1'in kümede görünmesi için doğrudan ilgilidir; Windows keşif ve firewall davranışı ayrı doğrulama ister.

**Durum:** 13 ileri / 34 geri; 24 değişen dosya; son commit `49b2c5f2`, 2026-05-03T01:58:39+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: make darwin mdns discovery reliable. Dosyalar: `dashboard/src/lib/components/GpuRichBar.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte`, `dashboard/src/lib/components/index.ts`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/connection-type.ts` ve 19 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/49b2c5f24e9ac7abac1bcc9e6275d7abc582ba8d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...49b2c5f24e9ac7abac1bcc9e6275d7abc582ba8d) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/reliable-mdns-discovery).


### 40. alexcheema/reproduce-gpu-lock

MLX GPU kilitlenmesini yeniden üretmek için bir betik ekler. MLX event leak düzeltmesi için bağımlılık ve ilgili çıkarım kodunu günceller.

**Windows katkısı:** M1/Metal hata teşhisi için referanstır; NVIDIA Windows GPU kilitlenmesini çözdüğü söylenemez.

**Durum:** 2 ileri / 195 geri; 6 değişen dosya; son commit `ccf4d91d`, 2026-02-24T09:44:07-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: add script to reproduce GPU lock issue. Dosyalar: `nix/mlx.nix`, `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/runner/llm_inference/runner.py`, `tmp/reproduce_gpu_lock.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ccf4d91d55f482f67a2e16659015033e9d8717fa) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ccf4d91d55f482f67a2e16659015033e9d8717fa) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/reproduce-gpu-lock).


### 41. alexcheema/restore-thunderbolt-bridge-launchdaemon

macOS Thunderbolt Bridge ağ kurulumunun LaunchDaemon yolunu geri getirir. Ağın hazır olması için 30 saniyelik bekleme ekler.

**Windows katkısı:** M1'in Mac ağ kurulumunu korumak için doğrudan ilgilidir; Windows Thunderbolt ağ sürücüsü çözümü değildir.

**Durum:** 2 ileri / 391 geri; 2 değişen dosya; son commit `501fb151`, 2026-01-23T15:29:39-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add 30s delay to wait for macOS network setup. Dosyalar: `app/EXO/EXO/EXOApp.swift`, `app/EXO/EXO/Services/NetworkSetupHelper.swift`. [Sabit commit](https://github.com/exo-explore/exo/commit/501fb151a57cbc35932385e369ab49d3f5301b93) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...501fb151a57cbc35932385e369ab49d3f5301b93) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/restore-thunderbolt-bridge-launchdaemon).


### 42. alexcheema/robust-hf-config-parsing

Özel modellerde model_id'yi temel kimlik yapan kart ve mimari destek düzenlemesidir. Hugging Face config'inden model özelliklerini çıkaran ve dahili kartları yeniden düzenleyen kapsamlı dosya değişiklikleri vardır.

**Windows katkısı:** Ortak model tanıma açısından ilgilidir; tanınan modelin Windows/CUDA veya M1'de yürütülebileceği ayrıca kontrol edilmelidir.

**Durum:** 2 ileri / 334 geri; 41 değişen dosya; son commit `8a184865`, 2026-02-05T06:05:31-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into alexcheema/robust-hf-config-parsing. Dosyalar: `src/exo/shared/constants.py`, `src/exo/shared/models/architecture_support.py`, `src/exo/shared/models/cards/deepseek-v3.1-4bit.json`, `src/exo/shared/models/cards/deepseek-v3.1-8bit.json`, `src/exo/shared/models/cards/glm-4.5-air-8bit.json` ve 36 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/8a184865650b88c74ebaec1ccca86934999daab6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8a184865650b88c74ebaec1ccca86934999daab6) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/robust-hf-config-parsing).


### 43. alexcheema/runner-health-check

RunnerSupervisor'a sağlık kontrolü ve heartbeat ekler. Docker tabanlı küme, çevrimdışı çalışma, chaos ve deterministik çıkarım e2e test altyapısını da içerir.

**Windows katkısı:** Karma kümede runner ölümü tespiti için yararlıdır; Linux Docker/iptables testleri yerel Windows doğrulaması sayılmaz.

**Durum:** 9 ileri / 272 geri; 17 değişen dosya; son commit `e5a8f39d`, 2026-02-16T11:11:30-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: add missing cancel_sender param to test supervisor builder. Dosyalar: `.dockerignore`, `.github/workflows/e2e.yml`, `conftest.py`, `e2e/Dockerfile`, `e2e/conftest.py` ve 12 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e5a8f39db6c39098030ae2b1421cee7727ddcdfd) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e5a8f39db6c39098030ae2b1421cee7727ddcdfd) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/runner-health-check).


### 44. alexcheema/speculative-decoding

Draft model kullanarak speculative decoding desteği ekler. Draft model ve draft token sayısını placement, instance, görev ve MLX yükleme akışından geçirir.

**Windows katkısı:** Mac MLX performans denemesi için adaydır; Windows/CUDA draft-target yürütmesini ayrıca uygulamak gerekir.

**Durum:** 6 ileri / 279 geri; 9 değişen dosya; son commit `3d4f8130`, 2026-02-13T09:39:11-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into alexcheema/speculative-decoding. Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `src/exo/master/main.py`, `src/exo/master/placement.py`, `src/exo/shared/apply.py`, `src/exo/shared/types/commands.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/3d4f8130c949644bd89ace3a62cf414cdd1cb271) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3d4f8130c949644bd89ace3a62cf414cdd1cb271) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/speculative-decoding).


### 45. alexcheema/topology-download-indicators

Topoloji düğümleri üzerinde model indirme durum göstergeleri ekler. Ana sayfa ve indirmeler sayfası ortak yardımcı kodla güncellenir.

**Windows katkısı:** Windows–Mac düğümlerinin indirme durumlarını izlemeyi kolaylaştırır; GPU veya taşıma platform desteğini değiştirmez.

**Durum:** 1 ileri / 339 geri; 4 değişen dosya; son commit `c381ae64`, 2026-02-04T06:07:48-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: show download status indicators on topology nodes. Dosyalar: `dashboard/src/lib/components/TopologyGraph.svelte`, `dashboard/src/lib/utils/downloads.ts`, `dashboard/src/routes/+page.svelte`, `dashboard/src/routes/downloads/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/c381ae64adc2317a485a3676cef4ae7310d4157e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c381ae64adc2317a485a3676cef4ae7310d4157e) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/topology-download-indicators).


### 46. alexcheema/trust-remote-code-cli-flag

Özel model tokenizer'ları için --trust-remote-code CLI seçeneği ekler. Dahili modellerin mevcut TRUST_REMOTE_CODE=True davranışını korur.

**Windows katkısı:** Model yükleme politikasını ortaklaştırmak için ilgilidir; Windows/CUDA backend sağlamaz ve M1 tokenizer davranışıyla birlikte değerlendirilmelidir.

**Durum:** 2 ileri / 194 geri; 3 değişen dosya; son commit `0dde45aa`, 2026-02-24T15:44:06Z. Açık PR: [#1605](https://github.com/exo-explore/exo/pull/1605).

**Kanıt:** Son commit: fix: keep TRUST_REMOTE_CODE=True for built-in models. Dosyalar: `src/exo/main.py`, `src/exo/worker/engines/mlx/constants.py`, `src/exo/worker/engines/mlx/utils_mlx.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/0dde45aa1fe4b877cfc035844ceee7fa4b5b85b9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0dde45aa1fe4b877cfc035844ceee7fa4b5b85b9) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/trust-remote-code-cli-flag).


### 47. alexcheema/unified-model-sources

Hugging Face, LM Studio, Ollama ve llama.cpp model kaynaklarını ortak katalog ve içerik tabanlı çözümleme altında toplar. Kaynak tarayıcıları, fingerprint testleri ve bozuk gossipsub mesajlarını düşüren router düzeltmesi ekler.

**Windows katkısı:** İki makinede mevcut model dosyalarını bulmak için önemli adaydır; katalog birleştirmek bu formatlara Windows/CUDA çıkarım motoru eklemek değildir.

**Durum:** 2 ileri / 36 geri; 33 değişen dosya; son commit `e0cc7b35`, 2026-05-01T16:14:10+01:00. Açık PR: [#2012](https://github.com/exo-explore/exo/pull/2012) (taslak).

**Kanıt:** Son commit: fix(routing): drop malformed gossipsub messages instead of crashing the receive loop. Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/downloads/+page.svelte`, `src/exo/api/main.py`, `src/exo/api/types/__init__.py`, `src/exo/api/types/api.py` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e0cc7b35138a70ddf1fd924e6007611c35302cad) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e0cc7b35138a70ddf1fd924e6007611c35302cad) · [Dal](https://github.com/exo-explore/exo/tree/alexcheema/unified-model-sources).


### 48. andrei/dgx-mac-usb-fix

DGX–Mac USB bağlantısı için Linux CDC-NCM/TAP yardımcıları, Nix shell wrapper'ları ve route A belgeleri geliştiren geniş deney dalıdır. Önceki vLLM/CUDA motoru çalışmaları da net farkta yer aldığından yalnız USB düzeltmesine indirgenemez.

**Windows katkısı:** NVIDIA–Mac ağ bağlantısı için fikir verir fakat DGX/Linux odaklı yol RTX 5070'li yerel Windows desteği sayılmaz.

**Durum:** 94 ileri / 139 geri; 150 değişen dosya; son commit `16295b29`, 2026-04-27T21:29:36+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Document DGX USB route A handoff state. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/pynvml/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi` ve 145 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/16295b29374d70a370134c8cf34a500541c95569) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...16295b29374d70a370134c8cf34a500541c95569) · [Dal](https://github.com/exo-explore/exo/tree/andrei/dgx-mac-usb-fix).


### 49. andrei/drain3

Drain3 ile log şablonu eğitimi için yardımcı modül ve komut satırı betiği ekler. Tip düzeltmeleri ve birim testleri de içerir.

**Windows katkısı:** Karma kümenin log analizine yardımcı olabilir; GPU motorları veya işletim sistemi uyumluluğunu değiştirmez.

**Durum:** 5 ileri / 11 geri; 3 değişen dosya; son commit `a323618e`, 2026-05-15T18:33:31+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Type Drain3 training script. Dosyalar: `scripts/drain3_train.py`, `src/exo/utils/drain3_training.py`, `src/exo/utils/tests/test_drain3_training.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a323618ec65efa0435592ea0f143de807d337eb1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a323618ec65efa0435592ea0f143de807d337eb1) · [Dal](https://github.com/exo-explore/exo/tree/andrei/drain3).


### 50. andrei/drytorch

CUDA/PyTorch/vLLM bağımlılıklarını Nix ortamında küçültmeye yönelik paketleme dalıdır. Sistem cuDNN/NCCL/NVSHMEM/cuSPARSELt kullanımı, gereksiz paketlerin çıkarılması ve gerekli Triton/FlashInfer parçalarının geri eklenmesi denenir.

**Windows katkısı:** RTX 5070 için CUDA bağımlılık tasarımı açısından ilgilidir; Linux/Nix paketleme çalışması yerel Windows build'i kanıtlamaz.

**Durum:** 13 ileri / 1 geri; 3 değişen dosya; son commit `26532424`, 2026-06-23T19:59:14+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: restore FlashInfer runtime package. Dosyalar: `flake.nix`, `pyproject.toml`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/26532424d34384ecd4a1a0b3cd4902e662ec51e8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...26532424d34384ecd4a1a0b3cd4902e662ec51e8) · [Dal](https://github.com/exo-explore/exo/tree/andrei/drytorch).


### 51. andrei/fix-2097

Master hata yolunda exception yükseltmek yerine error chunk göndermeyi düzenler. Agent skill dosyaları için gitignore değişikliği de vardır.

**Windows katkısı:** Ortak API hata geri bildirimi açısından yararlıdır; Windows veya M1 motor desteği eklemez.

**Durum:** 2 ileri / 11 geri; 2 değişen dosya; son commit `8a3e374d`, 2026-05-20T15:24:44+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: send error chunk instead of raising. Dosyalar: `.gitignore`, `src/exo/master/main.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/8a3e374d52f550c1e98aa759e514a133de5fa18f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8a3e374d52f550c1e98aa759e514a133de5fa18f) · [Dal](https://github.com/exo-explore/exo/tree/andrei/fix-2097).


### 52. andrei/force_oom

MLX'te çok büyük tensör işlemleriyle OOM üretme deneylerini ve macmon ölçüm değişikliklerini içerir. Kod yorumları Apple unified memory hedefini ve swap/kernel panic nedeniyle deneyin kararsızlığını açıkça belirtir.

**Windows katkısı:** M1 bellek hata teşhisi için deneysel referanstır; RTX 5070 çözümü veya M1'i korumak için doğrudan alınacak üretim yaması değildir.

**Durum:** 66 ileri / 13 geri; 6 değişen dosya; son commit `11f9d000`, 2026-05-15T13:53:11+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge branch 'main' into andrei/force_oom. Dosyalar: `.codex`, `.envrc`, `.idea/misc.xml`, `src/exo/shared/types/chunks.py`, `src/exo/utils/info_gatherer/macmon.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/11f9d000e52532586c3f10daefb26540169aff8d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...11f9d000e52532586c3f10daefb26540169aff8d) · [Dal](https://github.com/exo-explore/exo/tree/andrei/force_oom).


### 53. andrei/mlx-tinygrad-convert

MLX ile tinygrad arasında tensör aktarımı için bridge, lease pool ve stres testleri kurar. Torch/vLLM aktarım rotaları ile raw conversion benchmark'ları ve sonuç notları ekler.

**Windows katkısı:** Farklı motorlar arasında veri aktarımı için araştırma malzemesidir; Windows RTX 5070 ile M1 arasında hazır dağıtık çıkarım entegrasyonu göstermez.

**Durum:** 46 ileri / 51 geri; 20 değişen dosya; son commit `6c0ec0ef`, 2026-05-01T14:13:04+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: final. Dosyalar: `CONVERSION_BENCH_NOTES.md`, `flake.nix`, `mlx_tinygrad_interop/README.md`, `mlx_tinygrad_interop/__init__.py`, `mlx_tinygrad_interop/bench_raw_conversion.py` ve 15 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6c0ec0ef955a7ff9615bdcefa716228afd207c09) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6c0ec0ef955a7ff9615bdcefa716228afd207c09) · [Dal](https://github.com/exo-explore/exo/tree/andrei/mlx-tinygrad-convert).


### 54. andrei/py3-modules

PyO3 binding'lerini exo_rs Python paketi altında gerçek alt modüllere ayırır. Networking, kimlik ve pidfile girişleri, type stubları ve Nix Python paketleme düzeni değişir.

**Windows katkısı:** Windows portunda Rust/Python paket sınırını anlamak için önemlidir; platforma özgü ağ ve süreç kodunun taşındığını kanıtlamaz.

**Durum:** 8 ileri / 5 geri; 20 değişen dosya; son commit `9987bd01`, 2026-06-02T00:24:57+01:00. Açık PR: [#2139](https://github.com/exo-explore/exo/pull/2139).

**Kanıt:** Son commit: fmt. Dosyalar: `flake.nix`, `python/parts.nix`, `rust/exo_rs/pyproject.toml`, `rust/exo_rs/python/.gitignore`, `rust/exo_rs/python/exo_rs/__init__.py` ve 15 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9987bd01bd087b65edd3e399c27bbbed6eb18911) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9987bd01bd087b65edd3e399c27bbbed6eb18911) · [Dal](https://github.com/exo-explore/exo/tree/andrei/py3-modules).


### 55. andrei/py3-tracing

Snapshot'ta py3-modules ile aynı head ve commit serisini taşıyan Rust/Python modül düzenlemesidir. Dal adı tracing olsa da net değişiklik exo_rs alt modülleri ve paketleme çevresindedir.

**Windows katkısı:** Rust binding yapısı açısından ilgilidir; adından Windows tracing desteği çıkarılmamalıdır.

**Durum:** 8 ileri / 5 geri; 20 değişen dosya; son commit `9987bd01`, 2026-06-02T00:24:57+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fmt. Dosyalar: `flake.nix`, `python/parts.nix`, `rust/exo_rs/pyproject.toml`, `rust/exo_rs/python/.gitignore`, `rust/exo_rs/python/exo_rs/__init__.py` ve 15 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9987bd01bd087b65edd3e399c27bbbed6eb18911) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9987bd01bd087b65edd3e399c27bbbed6eb18911) · [Dal](https://github.com/exo-explore/exo/tree/andrei/py3-tracing).


### 56. andrei/rust-dx

Rust geliştirme deneyimi için flake, justfile ve Python paket parçalarını düzenler. Baş commit $REPO_ROOT kullanımının henüz çözülmediğini belirtir.

**Windows katkısı:** Geliştirme/paketleme referansıdır; yerel Windows çalıştırma yolu ve M1 davranışı konusunda yeni kanıt sunmaz.

**Durum:** 1 ileri / 3 geri; 4 değişen dosya; son commit `a685c04c`, 2026-06-03T21:58:01+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: basic shape - need to figure out how to get rid of $REPO_ROOT in the parts.nix. Dosyalar: `.gitignore`, `flake.nix`, `justfile`, `python/parts.nix`. [Sabit commit](https://github.com/exo-explore/exo/commit/a685c04cec0245f915bff384b391078da2cab07e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a685c04cec0245f915bff384b391078da2cab07e) · [Dal](https://github.com/exo-explore/exo/tree/andrei/rust-dx).


### 57. andrei/rust-settings

CLI ve ayarları Rust tarafına taşıyan geniş bir yeniden düzenlemedir. config.toml, seçeneklerin taşınması, yol/kimlik kalıcılığı, log/tracing ve Python erişimi üzerinde değişiklikler içerir.

**Windows katkısı:** Windows için config/yol düzeninin tasarımı açısından önemli, M1'de mevcut ayarların korunması açısından hassastır; tek başına Windows backend değildir.

**Durum:** 91 ileri / 3 geri; 62 değişen dosya; son commit `0abd91c6`, 2026-06-22T18:25:16+01:00. Açık PR: [#2163](https://github.com/exo-explore/exo/pull/2163).

**Kanıt:** Son commit: moved to using NewPy<T>. Dosyalar: `.github/workflows/build-app.yml`, `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `README.md` ve 57 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/0abd91c6cac0230352fb445b006cec1c41a93e95) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0abd91c6cac0230352fb445b006cec1c41a93e95) · [Dal](https://github.com/exo-explore/exo/tree/andrei/rust-settings).


### 58. andrei/telem

Runner crash loglarının isteğe bağlı telemetri yoluna bağlandığı MVP çalışmasıdır. Ana süreç, worker/supervisor ve telemetri testleri değişir.

**Windows katkısı:** İki platformda hata teşhisine yardımcı olabilir; platform çalıştırma desteği eklemez ve opt-in davranışı korunmalıdır.

**Durum:** 37 ileri / 5 geri; 7 değişen dosya; son commit `89e37929`, 2026-06-02T01:14:04+01:00. Açık PR: [#2126](https://github.com/exo-explore/exo/pull/2126).

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/andrei/telem' into andrei/telem. Dosyalar: `src/exo/main.py`, `src/exo/shared/constants.py`, `src/exo/shared/telemetry.py`, `src/exo/shared/tests/test_telemetry.py`, `src/exo/worker/main.py` ve 2 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/89e37929b69128a2babdecd1dd8bc030cb8788ed) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...89e37929b69128a2babdecd1dd8bc030cb8788ed) · [Dal](https://github.com/exo-explore/exo/tree/andrei/telem).


### 59. andrei/unix-socket-channel

Rust UnixStream tabanlı uzunluk önekli blob kanalları ile alt süreç haberleşmesini yeniden yazar. Async process, stdout/stderr yakalama, task group ve graceful shutdown düzenlemeleri de içerir.

**Windows katkısı:** std::os::unix ve dosya tanıtıcıları nedeniyle yerel Windows portunda doğrudan uyumsuzluk alanıdır; M1 süreç yolunu koruyarak ayrı taşıma gerekir.

**Durum:** 33 ileri / 32 geri; 12 değişen dosya; son commit `4dc9fa09`, 2026-05-06T14:54:28+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: format. Dosyalar: `.codex`, `rust/exo_pyo3_bindings/exo_pyo3_bindings.pyi`, `rust/exo_pyo3_bindings/src/blob_channel.rs`, `rust/exo_pyo3_bindings/src/lib.rs`, `rust/exo_pyo3_bindings/tests/test_python.py` ve 7 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/4dc9fa092c1462ba6fa4e730af38889bf00926f5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4dc9fa092c1462ba6fa4e730af38889bf00926f5) · [Dal](https://github.com/exo-explore/exo/tree/andrei/unix-socket-channel).


### 60. architecture-based-tokenizer-checks

Tokenizer yüklemesindeki model-ID metin eşleşmelerini mimariye dayalı kontrollerle değiştirir. Model kartı özellikleri, MLX yükleyici ve tokenizer testleri güncellenir.

**Windows katkısı:** M1/custom model yükleme doğruluğu için yararlıdır; Windows/CUDA çıkarım motoru sağlamaz.

**Durum:** 1 ileri / 260 geri; 3 değişen dosya; son commit `0c6e943c`, 2026-02-17T10:19:09-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: replace model ID string matching with architecture-based checks in tokenizer loading. Dosyalar: `src/exo/shared/models/model_cards.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/tests/unittests/test_mlx/test_tokenizers.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/0c6e943cea4f44325ca57dde1c493189178e8073) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0c6e943cea4f44325ca57dde1c493189178e8073) · [Dal](https://github.com/exo-explore/exo/tree/architecture-based-tokenizer-checks).


### 61. babbler

Rust babblerd ile yönlendirme, FIB, TUN, bağlantı profillemesi ve veri taşıma katmanı geliştiren geniş ağ deneyidir. Son commit'ler zorunlu TCP yolunu ve macOS listener/batching performansını düzeltir.

**Windows katkısı:** Karma kümenin TCP taşıması için araştırma adaydır; TUN/Babel ve platform ağ API'leri yerel Windows için ayrıca port ister.

**Durum:** 112 ileri / 11 geri; 46 değişen dosya; son commit `7a8153ec`, 2026-05-27T12:43:30+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: perf(dataplane): reduce TCP hot-path overhead. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `nix/babeld.nix` ve 41 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7a8153ecf397d50a8cf5cb9bb5dd33a9a4bdca01) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7a8153ecf397d50a8cf5cb9bb5dd33a9a4bdca01) · [Dal](https://github.com/exo-explore/exo/tree/babbler).


### 62. babbler-b

Babbler ağ deneyinin daha geniş alternatif dalıdır; PBProbe paket gönderme/alma ve Apple kernel timestamp optimizasyonları içerir. Çok sayıda bağımlılık, typing ve test farkı da bulunduğu için yalnız son build commit'ine indirgenemez.

**Windows katkısı:** Mac ağ ölçümü ve taşıma performansı için ilgilidir; Apple sendmsg_x/recvmsg_x gibi yollar yerel Windows uyumluluğu göstermez.

**Durum:** 97 ileri / 80 geri; 657 değişen dosya; son commit `a84d01c0`, 2026-05-19T19:07:47+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: it builds. Dosyalar: `.github/workflows/build-app.yml`, `.github/workflows/pipeline.yml`, `.gitignore`, `.idea/misc.xml`, `.typings/.gitkeep` ve 652 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a84d01c027ce8d556cf5a8f9d2be3483f0ff051b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a84d01c027ce8d556cf5a8f9d2be3483f0ff051b) · [Dal](https://github.com/exo-explore/exo/tree/babbler-b).


### 63. bench-context-scaling

Eco ile bütünleşen context uzunluğu ölçekleme benchmark akışı ekler. Campaign, çalıştırma/plot CLI'si ve warmup sayısı düzenlemesi ölçüm tekrarlanabilirliğini hedefler.

**Windows katkısı:** M1 ve RTX 5070 yollarını ayrı ölçmek için metodoloji sağlar; dalın kendisi Windows GPU motoru değildir.

**Durum:** 2 ileri / 23 geri; 31 değişen dosya; son commit `13ce4e90`, 2026-05-10T18:44:55+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Warmup = 2. Dosyalar: `AGENTS.md`, `README.md`, `bench/cli/__init__.py`, `bench/cli/__main__.py`, `bench/cli/_common.py` ve 26 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/13ce4e905264328850e48ae6fe2a389ed4cb7657) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...13ce4e905264328850e48ae6fe2a389ed4cb7657) · [Dal](https://github.com/exo-explore/exo/tree/bench-context-scaling).


### 64. bootstrap-peer

mDNS keşfini atlamak için --bootstrap-peer seçeneği ekler. Dal, MetaInstance yaşam döngüsü ve MLX dağıtık aktarım çalışmalarının geniş bir zincirini de içerir.

**Windows katkısı:** Windows–Mac keşif sorunlarında elle peer belirtme yararlı olabilir; bu seçenek hesaplama/taşıma backend uyumunu çözmez.

**Durum:** 45 ileri / 272 geri; 36 değişen dosya; son commit `9cacef39`, 2026-02-16T10:24:00-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add --bootstrap-peer flag to bypass mDNS for peer discovery. Dosyalar: `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `pyproject.toml` ve 31 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9cacef39f001957b79ba2317e2de001a42427eff) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9cacef39f001957b79ba2317e2de001a42427eff) · [Dal](https://github.com/exo-explore/exo/tree/bootstrap-peer).


### 65. bump-required-mem

Placement için model storage_size'ın üzerine yüzde 10 bellek payı ekler. Üzerinde başka placement olan düğümleri işaretleyip aday döngü değerlendirmesini de değiştirir.

**Windows katkısı:** RTX VRAM ve M1 unified memory planlamasına fikir verir; farklı bellek türlerini doğru modellediği ayrıca doğrulanmalıdır.

**Durum:** 2 ileri / 170 geri; 3 değişen dosya; son commit `2ab66e11`, 2026-03-03T16:45:08Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: or maybe this. Dosyalar: `src/exo/master/placement.py`, `src/exo/master/placement_utils.py`, `src/exo/shared/types/topology.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/2ab66e112d596a61ec6b583ba7fc0d7911783abe) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...2ab66e112d596a61ec6b583ba7fc0d7911783abe) · [Dal](https://github.com/exo-explore/exo/tree/bump-required-mem).


### 66. ciaran/download-coordinator-crash

İndirme koordinatörünün exception yolunu ele alır. Tek coordinator dosyasındaki değişiklik koordinatör çökmesini hedefler.

**Windows katkısı:** Her iki düğümde ortak indirme sağlamlığı için değerlidir; Windows/CUDA veya MLX motoruna yeni destek eklemez.

**Durum:** 1 ileri / 145 geri; 1 değişen dosya; son commit `8b2fb933`, 2026-03-13T13:15:28Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Handle download coordinator exception. Dosyalar: `src/exo/download/coordinator.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/8b2fb9330c2fc07748be5018909fe0b3e11ffd26) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8b2fb9330c2fc07748be5018909fe0b3e11ffd26) · [Dal](https://github.com/exo-explore/exo/tree/ciaran/download-coordinator-crash).


### 67. ciaran/handle-disconnects

Keşifte tek ping kaybı yerine n-strike toleransı kullanır. İndirme koordinatörü olaylarını worker kanalına bağlar ve partition recovery testleri ekler.

**Windows katkısı:** Karma kümenin geçici kopmalarda toparlanması için yararlıdır; yerel Windows hesaplama desteği değildir.

**Durum:** 3 ileri / 228 geri; 4 değişen dosya; son commit `c242671c`, 2026-02-20T14:00:27Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Test event dropping. Dosyalar: `rust/networking/src/discovery.rs`, `src/exo/download/coordinator.py`, `src/exo/main.py`, `src/exo/master/tests/test_partition_recovery.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/c242671cff1f60a6fe4724af9c51fc44df353c49) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c242671cff1f60a6fe4724af9c51fc44df353c49) · [Dal](https://github.com/exo-explore/exo/tree/ciaran/handle-disconnects).


### 68. ciaran/image-demo

Sohbette giriş görsellerini ve görsel boyutlarını gösterir. Placement seçiminde Thunderbolt bağlantısını önceliklendiren değişiklik de içerir.

**Windows katkısı:** Mac bağlantı ve görsel UI davranışı için örnektir; Windows–Mac çiftinde Thunderbolt yeteneği varsayılmamalıdır.

**Durum:** 3 ileri / 310 geri; 3 değişen dosya; son commit `164504fc`, 2026-02-10T11:41:44Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Show input images in chat. Dosyalar: `dashboard/src/lib/components/ChatMessages.svelte`, `dashboard/src/lib/components/ImageLightbox.svelte`, `src/exo/master/placement_utils.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/164504fc424b3c3b42707410cea9ac0c73a48d8e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...164504fc424b3c3b42707410cea9ac0c73a48d8e) · [Dal](https://github.com/exo-explore/exo/tree/ciaran/image-demo).


### 69. ciaran/storage-management

Model indirme ve yerel depolama yönetimi için limit, boş alan, retry ve durum adlarını düzenler. Download coordinator/shard downloader, state ve dashboard/Mac cluster gösterimi birlikte değişir.

**Windows katkısı:** Her iki makinede disk yönetimi için önemli adaydır; Windows dosya/yol davranışı ve M1 mevcut indirmeleri ayrıca korunmalıdır.

**Durum:** 23 ileri / 18 geri; 33 değişen dosya; son commit `65bd303e`, 2026-05-14T15:42:52+01:00. Açık PR: [#1675](https://github.com/exo-explore/exo/pull/1675).

**Kanıt:** Son commit: Resolve rebase. Dosyalar: `app/EXO/EXO/Models/ClusterState.swift`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/downloads.ts`, `dashboard/src/routes/+page.svelte`, `dashboard/src/routes/downloads/+page.svelte` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/65bd303ef6fe8eaf4fe163ccf2850e38eba50b3a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...65bd303ef6fe8eaf4fe163ccf2850e38eba50b3a) · [Dal](https://github.com/exo-explore/exo/tree/ciaran/storage-management).


### 70. codex/api-snapshot-bootstrap

API'nin başlangıç state'ini master snapshot'ından kurmasını ekler. Worker bootstrap, snapshot sunumu/alıcısı, şema sürümü ve event-buffer fast-forward zincirini de içerir.

**Windows katkısı:** Karma kümede hızlı ve tutarlı API açılışı için ilgilidir; GPU backend'inden bağımsızdır ve Windows çalışma desteği eklemez.

**Durum:** 8 ileri / 32 geri; 20 değişen dosya; son commit `ea045496`, 2026-05-03T01:39:54+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: bootstrap api state from snapshot. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_master.py` ve 15 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ea04549692d09625d87baca3a90c049fe413653b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ea04549692d09625d87baca3a90c049fe413653b) · [Dal](https://github.com/exo-explore/exo/tree/codex/api-snapshot-bootstrap).


### 71. codex/api-stream-reconcile-state

API stream'lerini State içeriğiyle yeniden uzlaştırır. Snapshot bootstrap ve özel model kartlarının state'te saklanıp uzlaştırılması da bu zincirin parçasıdır.

**Windows katkısı:** Windows–Mac yeniden bağlantılarında stream tutarlılığı için adaydır; motor uyumluluğuna doğrudan etkisi yoktur.

**Durum:** 11 ileri / 32 geri; 23 değişen dosya; son commit `7a25b418`, 2026-05-03T01:58:47+01:00. Açık PR: [#2027](https://github.com/exo-explore/exo/pull/2027).

**Kanıt:** Son commit: feat: reconcile api streams from state. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 18 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7a25b4186d763f39bec2abd7154333713087b382) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7a25b4186d763f39bec2abd7154333713087b382) · [Dal](https://github.com/exo-explore/exo/tree/codex/api-stream-reconcile-state).


### 72. codex/cluster-liveness-cadence

Küme canlılığı yoklama sıklığını ayarlar. Snapshot/NACK, worker backoff ve kalıcı-geçici olay ayrımı çalışmalarının üzerine kuruludur.

**Windows katkısı:** Karma kümede yeniden bağlantı gecikmesi ve kontrol trafiği açısından ilgilidir; Windows CUDA çalışmasını sağlamaz.

**Durum:** 19 ileri / 32 geri; 37 değişen dosya; son commit `6bcf4a99`, 2026-05-03T02:34:21+01:00. Açık PR: [#2035](https://github.com/exo-explore/exo/pull/2035).

**Kanıt:** Son commit: Tune cluster liveness polling cadence. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 32 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6bcf4a99f24d5fc0114e595ea87dbb7ca04a4b9a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6bcf4a99f24d5fc0114e595ea87dbb7ca04a4b9a) · [Dal](https://github.com/exo-explore/exo/tree/codex/cluster-liveness-cadence).


### 73. codex/custom-card-reconcile-retry

Özel model kartı reconciliation hatalarının yeniden denenmesini ekler. State/snapshot zinciri, canlılık ayarı ve worker geçici olaylarının boşaltılması da geçmişinde bulunur.

**Windows katkısı:** İki düğümde özel kartların tutarlı kalması için yararlıdır; kartın bulunması modelin Windows veya M1'de çalışacağı garantisi değildir.

**Durum:** 21 ileri / 32 geri; 37 değişen dosya; son commit `010e01ca`, 2026-05-03T02:39:57+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Retry custom card reconciliation failures. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 32 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/010e01cadc06da6e70d56b0a23049d6bc75f4fed) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...010e01cadc06da6e70d56b0a23049d6bc75f4fed) · [Dal](https://github.com/exo-explore/exo/tree/codex/custom-card-reconcile-retry).


### 74. codex/durable-event-boundary

Kalıcı olay günlüğünü state değişiklikleriyle sınırlar. Üretilen parçalar ve trace'leri geçici taşıma üzerinden geçirerek snapshot/state altyapısıyla bütünleştirir.

**Windows katkısı:** Karma kümede olay geçmişinin büyümesini azaltmaya yönelik mimari adaydır; hesaplama platformunu değiştirmez.

**Durum:** 17 ileri / 32 geri; 37 değişen dosya; son commit `6cece98e`, 2026-05-03T02:31:15+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Restrict durable events to state changes. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 32 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6cece98ec580c5f35c93f6200366b3f37bb3cbbe) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6cece98ec580c5f35c93f6200366b3f37bb3cbbe) · [Dal](https://github.com/exo-explore/exo/tree/codex/durable-event-boundary).


### 75. codex/event-router-fast-forward

Event router buffer'ının snapshot/ilerleme noktası üzerinden fast-forward yapmasını sağlar. Giriş parçalarının State'te saklanmasını da içerir.

**Windows katkısı:** Karma kümede eski olayların yeniden oynatılma maliyetini azaltabilir; Windows veya M1 motoru eklemez.

**Durum:** 2 ileri / 32 geri; 8 değişen dosya; son commit `f7bdef9f`, 2026-05-03T01:09:09+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: allow event router buffer fast-forward. Dosyalar: `src/exo/api/main.py`, `src/exo/routing/event_router.py`, `src/exo/routing/tests/test_event_buffer.py`, `src/exo/shared/apply.py`, `src/exo/shared/tests/test_apply/test_apply_input_chunks.py` ve 3 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/f7bdef9f085212f7556f5a5f2620c846102d81fd) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f7bdef9f085212f7556f5a5f2620c846102d81fd) · [Dal](https://github.com/exo-explore/exo/tree/codex/event-router-fast-forward).


### 76. codex/event-router-nack-tuning

Snapshot akışına uygun NACK yeniden isteme backoff'unu ayarlar. Kalıcı/geçici olay sınırı ve reconciliation çalışmalarının devamıdır.

**Windows katkısı:** Kayıp veya geciken ağ olaylarında karma kümenin kontrol trafiği açısından ilgilidir; Windows GPU portu değildir.

**Durum:** 18 ileri / 32 geri; 37 değişen dosya; son commit `3abd966d`, 2026-05-03T02:32:50+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Tune event router NACK backoff for snapshots. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 32 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/3abd966d75107193d4d839d5ce1912ef8735fe3a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3abd966d75107193d4d839d5ce1912ef8735fe3a) · [Dal](https://github.com/exo-explore/exo/tree/codex/event-router-nack-tuning).


### 77. codex/generated-chunks-transient

Üretilen token/görsel parçalarını geçici olay kanalından taşımaya geçirir. Snapshot ve API/worker state reconciliation altyapısı üzerine kuruludur.

**Windows katkısı:** İki makinenin streaming trafiğinde kalıcı olay yükünü azaltmak için adaydır; motorlar arası yürütme desteği eklemez.

**Durum:** 15 ileri / 32 geri; 31 değişen dosya; son commit `f10e6ab1`, 2026-05-03T02:24:36+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Route generated chunks over transient events. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 26 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/f10e6ab1b73021a44a6132001c7151292c2e830e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f10e6ab1b73021a44a6132001c7151292c2e830e) · [Dal](https://github.com/exo-explore/exo/tree/codex/generated-chunks-transient).


### 78. codex/input-chunks-state

Giriş parçalarını ortak State içinde saklar. API ve worker'ın bu veriyi state'ten ele almasını sağlayıp apply testleri ekler.

**Windows katkısı:** Karma kümede catch-up sonrası giriş verisi tutarlılığı için ilgilidir; Windows/CUDA çıkarım desteği sağlamaz.

**Durum:** 1 ileri / 32 geri; 5 değişen dosya; son commit `f792bd5d`, 2026-05-03T01:06:39+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: store input chunks in state. Dosyalar: `src/exo/api/main.py`, `src/exo/shared/apply.py`, `src/exo/shared/tests/test_apply/test_apply_input_chunks.py`, `src/exo/shared/types/state.py`, `src/exo/worker/main.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/f792bd5d520e3bcd2aeccd7b09a41676e1e5e366) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f792bd5d520e3bcd2aeccd7b09a41676e1e5e366) · [Dal](https://github.com/exo-explore/exo/tree/codex/input-chunks-state).


### 79. codex/master-snapshot-serving

Master'ın state snapshot'larını sunmasını ekler. Snapshot routing tipleri, alıcı, şema sürümü ve buffer fast-forward altyapısı da bu dala dahildir.

**Windows katkısı:** Windows–Mac düğümlerinin state'i hızlı edinmesi için değerlidir; backend uyumluluğundan bağımsızdır.

**Durum:** 6 ileri / 32 geri; 18 değişen dosya; son commit `24c56138`, 2026-05-03T01:18:29+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: serve state snapshots from master. Dosyalar: `src/exo/api/main.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_master.py`, `src/exo/routing/event_router.py` ve 13 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/24c56138e32583d7dfc26292bcbf0f845394616a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...24c56138e32583d7dfc26292bcbf0f845394616a) · [Dal](https://github.com/exo-explore/exo/tree/codex/master-snapshot-serving).


### 80. codex/snapshot-receiver

State snapshot'larını alan ve uygulayan receiver bileşeni ekler. Sürümleme, giriş parçaları ve event buffer fast-forward değişiklikleriyle birlikte gelir.

**Windows katkısı:** Karma kümede yeniden katılma/catch-up için adaydır; yeni GPU veya işletim sistemi desteği vermez.

**Durum:** 4 ileri / 32 geri; 12 değişen dosya; son commit `343d5bc6`, 2026-05-03T01:13:48+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add snapshot receiver. Dosyalar: `src/exo/api/main.py`, `src/exo/routing/event_router.py`, `src/exo/routing/snapshot_receiver.py`, `src/exo/routing/tests/test_event_buffer.py`, `src/exo/routing/tests/test_snapshot_receiver.py` ve 7 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/343d5bc6d4f9b9745b00be386db4c30c6f0c917d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...343d5bc6d4f9b9745b00be386db4c30c6f0c917d) · [Dal](https://github.com/exo-explore/exo/tree/codex/snapshot-receiver).


### 81. codex/snapshot-routing-types

Snapshot istek/yanıtlarının routing tiplerini ve topic bağlantısını ekler. Önceki snapshot receiver ve state sürümleme zincirini içerir.

**Windows katkısı:** Windows–Mac kontrol protokolü açısından ilgilidir; hesaplama backend'inin Windows uyumunu değiştirmez.

**Durum:** 5 ileri / 32 geri; 16 değişen dosya; son commit `c89caaf8`, 2026-05-03T01:15:46+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add snapshot routing types. Dosyalar: `src/exo/api/main.py`, `src/exo/master/main.py`, `src/exo/routing/event_router.py`, `src/exo/routing/snapshot_receiver.py`, `src/exo/routing/tests/test_event_buffer.py` ve 11 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/c89caaf87a0ad55c13c98b7430fa374e03c864fa) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c89caaf87a0ad55c13c98b7430fa374e03c864fa) · [Dal](https://github.com/exo-explore/exo/tree/codex/snapshot-routing-types).


### 82. codex/state-schema-version

State snapshot şemasına sürümleme ekler. Serileştirme testleri, giriş parçalarının saklanması ve router fast-forward akışı birlikte değişir.

**Windows katkısı:** İki makinenin state şeması uyumu için yararlıdır; model motoru veya yerel Windows desteği eklemez.

**Durum:** 3 ileri / 32 geri; 9 değişen dosya; son commit `0e6a56ba`, 2026-05-03T01:12:31+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: version state snapshots. Dosyalar: `src/exo/api/main.py`, `src/exo/routing/event_router.py`, `src/exo/routing/tests/test_event_buffer.py`, `src/exo/shared/apply.py`, `src/exo/shared/tests/test_apply/test_apply_input_chunks.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/0e6a56baee940484bfa76f129af98de555183907) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0e6a56baee940484bfa76f129af98de555183907) · [Dal](https://github.com/exo-explore/exo/tree/codex/state-schema-version).


### 83. codex/traces-transient

Trace olaylarını geçici transport'a taşır. Üretilen parçaların geçici yolu ve snapshot/reconciliation altyapısı da dal zincirine dahildir.

**Windows katkısı:** Karma kümede trace trafiğini kalıcı state geçmişinden ayırmak için ilgilidir; Windows GPU desteğine doğrudan katkısı yoktur.

**Durum:** 16 ileri / 32 geri; 31 değişen dosya; son commit `3249d410`, 2026-05-03T02:27:32+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Route traces over transient events. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 26 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/3249d41098f7ceddc79d8a69b796ca1fea4b0b10) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3249d41098f7ceddc79d8a69b796ca1fea4b0b10) · [Dal](https://github.com/exo-explore/exo/tree/codex/traces-transient).


### 84. codex/transient-event-transport

Kalıcı state olaylarından ayrı geçici olay transport'u ekler. API stream'leri, özel model kartları ve worker backoff'un state'ten uzlaştırılması da bu aşamaya kadar olan zincirdedir.

**Windows katkısı:** Windows–Mac ortak kontrol protokolü için mimari adaydır; platforma özgü transport ve GPU çalışması ayrıca doğrulanmalıdır.

**Durum:** 13 ileri / 32 geri; 29 değişen dosya; son commit `62fd3ae3`, 2026-05-03T02:03:58+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add transient event transport. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 24 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/62fd3ae36ca666fd583288ef2ebe2e30d09ca150) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...62fd3ae36ca666fd583288ef2ebe2e30d09ca150) · [Dal](https://github.com/exo-explore/exo/tree/codex/transient-event-transport).


### 85. codex/transient-router-wiring

Geçici olay router'ını düğümün başlangıç/kapanış yaşam döngüsüne bağlar. Transport ve snapshot tabanlı API/worker reconciliation çalışmalarını taşır.

**Windows katkısı:** Karma kümede yeni olay yolunun yaşam döngüsünü tutarlı kılar; Windows/CUDA motorunu sağlamaz.

**Durum:** 14 ileri / 32 geri; 29 değişen dosya; son commit `7f229425`, 2026-05-03T02:19:13+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Wire transient router through node lifecycle. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 24 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7f229425d6fed7e756ce2cb50d493c7fb8b2b1f6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7f229425d6fed7e756ce2cb50d493c7fb8b2b1f6) · [Dal](https://github.com/exo-explore/exo/tree/codex/transient-router-wiring).


### 86. codex/worker-backoff-reconcile-state

Worker instance backoff bilgisini State'ten yeniden uzlaştırır. Snapshot bootstrap, API stream ve özel model kartı reconciliation zincirine dayanır.

**Windows katkısı:** Karma kümede worker yeniden başlatma/toparlanma için ilgilidir; M1 veya Windows GPU backend'i eklemez.

**Durum:** 12 ileri / 32 geri; 26 değişen dosya; son commit `c0d4fd7f`, 2026-05-03T02:01:08+01:00. Açık PR: [#2028](https://github.com/exo-explore/exo/pull/2028).

**Kanıt:** Son commit: feat: reconcile worker backoff from state. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 21 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/c0d4fd7fa7a4770eff7877e19dd1c678bbae8a86) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c0d4fd7fa7a4770eff7877e19dd1c678bbae8a86) · [Dal](https://github.com/exo-explore/exo/tree/codex/worker-backoff-reconcile-state).


### 87. codex/worker-drain-transients

Worker'ın kullanmadığı geçici olayları tüketip boşaltmasını ekler. Canlılık sıklığı, NACK ve kalıcı/geçici olay ayrımı çalışmalarının devamıdır.

**Windows katkısı:** Karma kümede tüketilmeyen olayların birikmesini önlemek için adaydır; işletim sistemi veya motor desteğini değiştirmez.

**Durum:** 20 ileri / 32 geri; 37 değişen dosya; son commit `9ca8ac13`, 2026-05-03T02:37:19+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Drain unused worker transient events. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_api_snapshot_bootstrap.py`, `src/exo/api/tests/test_instance_deleted_stream_cleanup.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 32 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9ca8ac133b322bb98f918fb2c0fe4f8ddf094081) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9ca8ac133b322bb98f918fb2c0fe4f8ddf094081) · [Dal](https://github.com/exo-explore/exo/tree/codex/worker-drain-transients).


### 88. codex/worker-snapshot-bootstrap

Worker'ın başlangıç state'ini snapshot üzerinden kurmasını ekler. Master sunumu, alıcı/routing tipleri, şema sürümü ve fast-forward altyapısını içerir.

**Windows katkısı:** M1 ve Windows düğümlerinin yeniden katılması için ortak mimari katkıdır; Windows çalıştırma yolu ayrıca gerekir.

**Durum:** 7 ileri / 32 geri; 19 değişen dosya; son commit `a2c2a0fc`, 2026-05-03T01:35:43+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: bootstrap worker state from snapshot. Dosyalar: `src/exo/api/main.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_master.py`, `src/exo/routing/event_router.py` ve 14 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a2c2a0fc92c8d6be510d385b1aefc843c8717b59) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a2c2a0fc92c8d6be510d385b1aefc843c8717b59) · [Dal](https://github.com/exo-explore/exo/tree/codex/worker-snapshot-bootstrap).


### 89. consistent-placement-api

Instance tiplerine instance_meta ve sharding bilgisini ekleyip placement API yanıtlarını tutarlı hale getirir. MLX Ring/JACCL ile pipeline/tensor metadata ayrımı açıkça ifade edilir.

**Windows katkısı:** Karma kümenin motor/taşıma yeteneklerini açık modellemesine fikir verir; mevcut tipler Windows CUDA motoru değildir.

**Durum:** 1 ileri / 182 geri; 2 değişen dosya; son commit `525aaab8`, 2026-02-26T13:42:07Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix. Dosyalar: `src/exo/master/api.py`, `src/exo/shared/types/worker/instances.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/525aaab8085e41935ed90663da1db7cab3baa9a8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...525aaab8085e41935ed90663da1db7cab3baa9a8) · [Dal](https://github.com/exo-explore/exo/tree/consistent-placement-api).


### 90. cuda-build-improvement

Nix CUDA paketlerinin NVIDIA sürücü kütüphanelerini bulması için autoAddDriverRunpath düzenlemesi yapar. nix-gl-host wrapper'ını kaldırıp Linux libcuda.so bağımlılık/paketleme davranışını değiştirir.

**Windows katkısı:** RTX 5070 için CUDA paketleme referansıdır fakat Linux/Nix odaklıdır; yerel Windows desteği veya M1 ile ortak çıkarım kanıtı sunmaz.

**Durum:** 1 ileri / 45 geri; 3 değişen dosya; son commit `7f99e4e5`, 2026-04-25T01:52:33+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: todo once mlx is fixed. Dosyalar: `flake.lock`, `flake.nix`, `python/parts.nix`. [Sabit commit](https://github.com/exo-explore/exo/commit/7f99e4e5c501de750d19db09c5a33d3e04384d35) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7f99e4e5c501de750d19db09c5a33d3e04384d35) · [Dal](https://github.com/exo-explore/exo/tree/cuda-build-improvement).


### 91. dashboard-show-failure-reasons

Runner ve indirme hatalarının nedenlerini dashboard'da gösterir. Ana ve indirmeler sayfaları hata geri bildirimi için güncellenir.

**Windows katkısı:** Windows–Mac kümesinde hata teşhisini kolaylaştırır; GPU/işletim sistemi uyumluluğunu değiştirmez.

**Durum:** 1 ileri / 267 geri; 2 değişen dosya; son commit `6a077234`, 2026-02-17T09:59:06-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: dashboard: show failure reasons for runner and download errors (#1350). Dosyalar: `dashboard/src/routes/+page.svelte`, `dashboard/src/routes/downloads/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/6a077234142f4a3ea2d1ba13e89023ceb420eac5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6a077234142f4a3ea2d1ba13e89023ceb420eac5) · [Dal](https://github.com/exo-explore/exo/tree/dashboard-show-failure-reasons).


### 92. david/attn-moe-split

Qwen3.5 attention ile MoE hesaplamasını ayıran MLX pipeline/patch çalışmaları ve MTP/DFlash speculative yollarını içerir. Son commit'ler MTP ağırlıklarını byte-range ile indirmeyi ve mtp. anahtar önekini korumayı düzeltir.

**Windows katkısı:** M1 MLX performans araştırması için kapsamlı deneydir; Metal/MLX kernel çalışmalarını RTX 5070 yerel Windows'a hazır destek diye yorumlamak doğru olmaz.

**Durum:** 148 ileri / 102 geri; 71 değişen dosya; son commit `7002cb79`, 2026-04-22T11:56:21+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: batch_generate: preserve 'mtp.' prefix in cached MTP weights (was a real bug). Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `resources/inference_model_cards/mlx-community--Qwen3.5-27B-bf16.toml`, `src/exo/api/main.py`, `src/exo/master/placement.py` ve 66 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7002cb79dceb5e8450ed2e3b3951578e42243ad5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7002cb79dceb5e8450ed2e3b3951578e42243ad5) · [Dal](https://github.com/exo-explore/exo/tree/david/attn-moe-split).


### 93. david/batched-kernels

Qwen3.5/MoE için batch ve fused MLX kernel'leri ekler. Tensor parallel shard sonrasında patch uygulaması, residual ölçekleme ve boyutların ağırlık shape'inden okunmasıyla doğruluk sorunlarını hedefler.

**Windows katkısı:** M1 performans ve doğruluğu için incelenebilir; MLX kernel'lerinin RTX 5070/Windows'ta çalışması ayrıca kanıt ister.

**Durum:** 29 ileri / 139 geri; 56 değişen dosya; son commit `31075385`, 2026-05-02T19:04:48+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: qwen3_5_moe/common: read MoE dims from weight.shape (TP correctness). Dosyalar: `.mlx_typings/mlx/core/__init__.pyi`, `.mlx_typings/mlx/nn/__init__.pyi`, `.mlx_typings/mlx/nn/layers/__init__.pyi`, `.mlx_typings/mlx/nn/layers/base.pyi`, `.mlx_typings/mlx_lm/generate.pyi` ve 51 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/31075385fc7df73ac588bd777e939bbc8b03b311) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...31075385fc7df73ac588bd777e939bbc8b03b311) · [Dal](https://github.com/exo-explore/exo/tree/david/batched-kernels).


### 94. david/batched-kernels-on-main

Batched/fused MoE kernel çalışmasını main'e daha yakın bir tabana taşır ve tensor-parallel prefill/residual davranışını düzeltir. A/B patch açma-kapama, decode zamanlama dökümü ve benchmark tekrar logları da içerir.

**Windows katkısı:** M1 MLX yolunda ölçüm ve performans karşılaştırması için adaydır; yerel Windows CUDA portu değildir.

**Durum:** 10 ileri / 32 geri; 25 değişen dosya; son commit `35454112`, 2026-05-05T02:14:37+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Revert "Disable apply_batch_gen_patch for A/B (opt_batch_gen wrapper)". Dosyalar: `bench/exo_bench.py`, `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/generator/batch_generate.py`, `src/exo/worker/engines/mlx/patches/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/__init__.py` ve 20 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/35454112a5e4fba50a555ab9bb5679ac58c1decc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...35454112a5e4fba50a555ab9bb5679ac58c1decc) · [Dal](https://github.com/exo-explore/exo/tree/david/batched-kernels-on-main).


### 95. david/lcb_eval

LiveCodeBench (LCB) ile uyumlu, karşılaştırılabilir kod üretimi değerlendirmesi ekler. bench/exo_eval.py veri sırasını resmî question_id düzenine uyarlar; örnekleme seçenekleri, repetition penalty varsayılanı ve float32 log olasılığı için mlx-lm bağımlılığı da değişir.

**Windows katkısı:** Değerlendirme yöntemi RTX 5070 sonuçlarını M1 ile karşılaştırmaya uyarlanabilir; mevcut MLX bağımlılığı yerel Windows çalıştırma kanıtı değildir.

**Durum:** 6 ileri / 154 geri; 2 değişen dosya; son commit `acb48180`, 2026-03-11T09:02:29-07:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Point mlx-lm to fix/float32-logprobs branch for float32 log_softmax fix. Dosyalar: `bench/exo_eval.py`, `pyproject.toml`. [Sabit commit](https://github.com/exo-explore/exo/commit/acb4818057a5ac8a6c3d8a4b634370bde474fd98) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...acb4818057a5ac8a6c3d8a4b634370bde474fd98) · [Dal](https://github.com/exo-explore/exo/tree/david/lcb_eval).


### 96. david/mla-context-parallel

DeepSeek'in MLA (Multi-head Latent Attention) katmanlarında bağlamı düğümlere bölerek uzun girişleri paralel işleme deneyidir. MLX sharding, batched/scoring runner ve değerlendirme kodunu birlikte değiştirir; Qwen3Next ve MiniMax attention düzenlemeleri de taşır.

**Windows katkısı:** M1 üzerindeki uzun bağlam araştırması için adaydır; MLX'e dayalı bu çalışma heterojen CUDA–Metal veya yerel Windows desteğini göstermiyor.

**Durum:** 42 ileri / 375 geri; 26 değişen dosya; son commit `6018a9c9`, 2026-02-02T19:16:43Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Point mlx-lm to davidmcc73 fork with context parallelism support. Dosyalar: `bench/__init__.py`, `bench/eval_config.toml`, `bench/exo_eval.py`, `bench/lm_eval_patched.py`, `bench/stats_dashboard.html` ve 21 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6018a9c97c02b4dd9996fc517ecc263e52fe392e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6018a9c97c02b4dd9996fc517ecc263e52fe392e) · [Dal](https://github.com/exo-explore/exo/tree/david/mla-context-parallel).


### 97. david/new-kernels

Qwen3.5 MoE için attention, normalizasyon, projection ve uzman hesaplarını birleştiren özel MLX/Metal çekirdekleri ekler. Son commitler skaler girdileri Metal kaynak sabitlerine taşır ve RoPE/cache_offset tür sorunlarını düzeltir.

**Windows katkısı:** Korunan M1/Metal yolu açısından performans araştırmasıdır; Metal çekirdekleri RTX 5070 CUDA motoruna doğrudan taşınamaz.

**Durum:** 15 ileri / 156 geri; 23 değişen dosya; son commit `3a1fc000`, 2026-03-15T13:20:21Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Bake scale into SDPA pass1 source, remove last scalar input. Dosyalar: `src/exo/worker/engines/mlx/patches/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/apply.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/common.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/decoder.py` ve 18 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/3a1fc000f98a107f3c29818ae747b71f8d7200ec) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3a1fc000f98a107f3c29818ae747b71f8d7200ec) · [Dal](https://github.com/exo-explore/exo/tree/david/new-kernels).


### 98. david/new-kernels-v2

Qwen3.5 MoE için özel, birleştirilmiş MLX/Metal çekirdeklerinin ikinci dal varyantıdır. Envanterde new-kernels ile aynı dosya ailesi ve son sekiz commit konusu görünür; ayrılan toplam commit sayısı farklıdır.

**Windows katkısı:** M1 performans hattıyla ilgilidir; v2 adı Windows veya CUDA uygulaması anlamına gelmez.

**Durum:** 14 ileri / 157 geri; 23 değişen dosya; son commit `45c0bb02`, 2026-03-15T14:57:02Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Bake scale into SDPA pass1 source, remove last scalar input. Dosyalar: `src/exo/worker/engines/mlx/patches/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/apply.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/common.py`, `src/exo/worker/engines/mlx/patches/qwen3_5_moe/decoder.py` ve 18 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/45c0bb02895aa0b4958a89cfe7ae976652708cf0) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...45c0bb02895aa0b4958a89cfe7ae976652708cf0) · [Dal](https://github.com/exo-explore/exo/tree/david/new-kernels-v2).


### 99. david/no-patch-tensor-model

patch_tensor_model optimizasyonunu kapatarak tensor-parallel davranışı A/B karşılaştırmaya açar. Benchmark her tekrarın sonuçlarını kaydeder ve temperature=0 ile argmax örneklemesinin ek maliyetini azaltır.

**Windows katkısı:** M1 tarafındaki MLX optimizasyonlarının etkisini ayırmak için yararlıdır; NVIDIA motoruna yeni yetenek eklemez.

**Durum:** 3 ileri / 32 geri; 2 değişen dosya; son commit `00993ada`, 2026-05-05T00:36:32+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: exo_bench: set temperature=0.0 for argmax sampling (drops decode overhead). Dosyalar: `bench/exo_bench.py`, `src/exo/worker/engines/mlx/auto_parallel.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/00993ada81593338238e97d19e8fabb300fcf9c3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...00993ada81593338238e97d19e8fabb300fcf9c3) · [Dal](https://github.com/exo-explore/exo/tree/david/no-patch-tensor-model).


### 100. david/speculative-mtp

Qwen3.5 için MTP (Multi-Token Prediction) tabanlı speculative decoding ekler. Taslak tokenları toplu doğrulayan generator, speculative cache ve birleşik MLX çekirdek yamalarını tek committe taşır.

**Windows katkısı:** M1 decode hızlandırması için araştırılabilir; CUDA/Windows ve M1 arasında ortak speculative motor kanıtı bulunmuyor.

**Durum:** 1 ileri / 104 geri; 30 değişen dosya; son commit `784662f4`, 2026-03-31T00:04:54+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: MTP speculative decoding + kernel patches for Qwen3.5 (rebased on main). Dosyalar: `src/exo/worker/engines/mlx/generator/batch_generate.py`, `src/exo/worker/engines/mlx/patches/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5/__init__.py`, `src/exo/worker/engines/mlx/patches/qwen3_5/custom_qmv_loop_over_b.py`, `src/exo/worker/engines/mlx/patches/qwen3_5/lpb_patch.py` ve 25 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/784662f40a75b56c5c1c347c2c26775cb720bd68) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...784662f40a75b56c5c1c347c2c26775cb720bd68) · [Dal](https://github.com/exo-explore/exo/tree/david/speculative-mtp).


### 101. david/speculative-v2

MTP üzerine DFlash speculative decoding modu ve drafter çekirdeklerini önceden derleyen warmup ekler. Dinamik matmul çekirdeği seçimi ile Qwen3.5-27B bf16 desteği de aynı dalda yer alır.

**Windows katkısı:** M1 üzerindeki MLX speculative çalışmasıyla ilgilidir; bf16 model kartı RTX 5070 ya da native Windows desteği sağlamaz.

**Durum:** 8 ileri / 102 geri; 57 değişen dosya; son commit `051d6005`, 2026-04-14T18:35:10+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: DFlash warmup: full S_ctx sweep to pre-compile every drafter kernel. Dosyalar: `resources/inference_model_cards/mlx-community--Qwen3.5-27B-bf16.toml`, `src/exo/worker/engines/mlx/generator/batch_generate.py`, `src/exo/worker/engines/mlx/matmul/__init__.py`, `src/exo/worker/engines/mlx/matmul/kernels/__init__.py`, `src/exo/worker/engines/mlx/matmul/kernels/bf16/__init__.py` ve 52 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/051d60059ed227bb6f4d0fe262b236a1801e566f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...051d60059ed227bb6f4d0fe262b236a1801e566f) · [Dal](https://github.com/exo-explore/exo/tree/david/speculative-v2).


### 102. distributed-settings

Yerel klasörler, model ayarları ve küme ayarlarını tipli bir yapı altında toplama taslağıdır. pydantic-settings ile TOML/ortam değişkeni kaynakları ve ayar birleştirme kuralları eklenir; get_local/get_cluster gövdeleri henüz yer tutucudur.

**Windows katkısı:** Windows ve Mac yapılandırmasını düzenleme fikri yararlıdır, ancak iki noktayla klasör bölme Windows sürücü yolları için ayrıca uyarlanmalıdır.

**Durum:** 1 ileri / 55 geri; 4 değişen dosya; son commit `efa0da09`, 2026-04-22T12:51:10+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: wah. Dosyalar: `pyproject.toml`, `src/exo/shared/constants.py`, `src/exo/shared/settings.py`, `src/exo/utils/dashboard_path.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/efa0da09124625be5170875eedea12811992a2cf) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...efa0da09124625be5170875eedea12811992a2cf) · [Dal](https://github.com/exo-explore/exo/tree/distributed-settings).


### 103. docker-images

Nix derlemesine Docker image üretimini ve ilgili CI adımlarını ekler. Son commit Cachix'e gönderimi kapatır; python/parts.nix ve ortak sabitler de değişir.

**Windows katkısı:** Konteyner dağıtımı için örnek olabilir; Docker/Linux yolu native Windows RTX 5070 kabulünün yerine geçmez.

**Durum:** 2 ileri / 28 geri; 3 değişen dosya; son commit `8a286648`, 2026-05-07T09:07:51+01:00. Açık PR: [#1954](https://github.com/exo-explore/exo/pull/1954).

**Kanıt:** Son commit: dont push to cachix. Dosyalar: `.github/workflows/pipeline.yml`, `python/parts.nix`, `src/exo/shared/constants.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/8a286648463bce61bc5f732f694938e74dc96cf3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8a286648463bce61bc5f732f694938e74dc96cf3) · [Dal](https://github.com/exo-explore/exo/tree/docker-images).


### 104. e2e-tests

Docker tabanlı uçtan uca küme oluşumu, çevrimdışı çalışma, inference snapshot ve runner chaos testleri ekler. Darwin CI tekrarları, ağ kaynaklı flaky test yeniden denemesi ve runner cancellation helper uyarlamaları da taşır.

**Windows katkısı:** Windows–M1 kabul senaryolarına test fikri sağlar; Docker/Darwin test kapsamı yerel Windows NVIDIA yolunu doğrulamış sayılmaz.

**Durum:** 23 ileri / 272 geri; 24 değişen dosya; son commit `a288401a`, 2026-02-16T10:25:22-08:00. Açık PR: [#1462](https://github.com/exo-explore/exo/pull/1462).

**Kanıt:** Son commit: fix: pass _cancel_sender in RunnerSupervisor test helper. Dosyalar: `.dockerignore`, `.github/workflows/e2e.yml`, `conftest.py`, `e2e/Dockerfile`, `e2e/conftest.py` ve 19 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a288401a7f0b7db237c04073a3bdcd6879a0c3dc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a288401a7f0b7db237c04073a3bdcd6879a0c3dc) · [Dal](https://github.com/exo-explore/exo/tree/e2e-tests).


### 105. feat/bandwidth-aware-placement

Pipeline katman paylarını yalnız bellek kapasitesine göre değil ölçülen bellek bant genişliğine göre dağıtır. Profil warmup ve 2 GB tamponla ölçümü iyileştirir; placement_utils ile shard atama testleri değişir.

**Windows katkısı:** RTX 5070 ile M1 arasında dengesiz hızları hesaba katma fikri önemlidir; MLX profilinin Windows GPU bant genişliği ölçümüne uyarlanması gerekir.

**Durum:** 8 ileri / 453 geri; 5 değişen dosya; son commit `4d414556`, 2026-01-16T15:33:18Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Use 2GB buffer for more accurate bandwidth measurement. Dosyalar: `src/exo/master/placement_utils.py`, `src/exo/master/tests/test_placement_utils.py`, `src/exo/shared/types/profiling.py`, `src/exo/worker/utils/profile.py`, `src/exo/worker/utils/system_info.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/4d414556d50f383f245766a4e8cf592f6227eb87) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4d414556d50f383f245766a4e8cf592f6227eb87) · [Dal](https://github.com/exo-explore/exo/tree/feat/bandwidth-aware-placement).


### 106. feat/dashboard-light-mode

Dashboard'a açık/koyu tema anahtarı ekler. Genel CSS ile sohbet, model kartı, topology ve indirme bileşenlerinin renklerini temaya uyarlar.

**Windows katkısı:** Windows ve M1 tarayıcı arayüzünde aynı kullanılabilirlik iyileştirmesidir; inference motoruna etkisi yoktur.

**Durum:** 2 ileri / 252 geri; 13 değişen dosya; son commit `99b0db06`, 2026-02-18T11:46:00-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: chore: apply nix fmt formatting to svelte files. Dosyalar: `dashboard/src/app.css`, `dashboard/src/app.html`, `dashboard/src/lib/components/ChatAttachments.svelte`, `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/lib/components/ChatMessages.svelte` ve 8 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/99b0db06349b74e968bf9181a493def56db5fef1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...99b0db06349b74e968bf9181a493def56db5fef1) · [Dal](https://github.com/exo-explore/exo/tree/feat/dashboard-light-mode).


### 107. feat/dashboard-light-mode-v2

Açık/koyu tema için ayrı theme store ve sıcak parşömen paleti kullanan ikinci uygulamadır. Header, ModelCard ve TopologyGraph tema durumunu izler; layout başlangıç ayarını yapar.

**Windows katkısı:** Her iki makinenin dashboard kullanımına yararlıdır; RTX 5070 veya Windows backend desteği eklemez.

**Durum:** 2 ileri / 225 geri; 7 değişen dosya; son commit `ab427f1b`, 2026-02-20T08:56:51-08:00. Açık PR: [#1535](https://github.com/exo-explore/exo/pull/1535).

**Kanıt:** Son commit: feat(dashboard): add light-mode theme awareness to ModelCard and TopologyGraph. Dosyalar: `dashboard/src/app.css`, `dashboard/src/app.html`, `dashboard/src/lib/components/HeaderNav.svelte`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte` ve 2 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ab427f1b75db14cf0ca2ba0d84b8abf5eab5d979) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ab427f1b75db14cf0ca2ba0d84b8abf5eab5d979) · [Dal](https://github.com/exo-explore/exo/tree/feat/dashboard-light-mode-v2).


### 108. feat/e2e-chaos-tests

Docker E2E altyapısına istemci kopması, eşzamanlı istek, dağıtık yükleme, hata toparlanması ve düğüm giriş/çıkış chaos testleri ekler. e2e-tests ile ortak değişiklikler yanında src/exo/tests/e2e_chaos test paketi bulunur.

**Windows katkısı:** Windows–M1 kümesinin kopma ve toparlanma kabul testlerine uygun örnektir; native Windows çalıştırıldığına dair kanıt değildir.

**Durum:** 24 ileri / 272 geri; 33 değişen dosya; son commit `23d5b335`, 2026-02-20T07:03:55-08:00. Açık PR: [#1545](https://github.com/exo-explore/exo/pull/1545).

**Kanıt:** Son commit: feat: add E2E chaos/networking tests. Dosyalar: `.dockerignore`, `.github/workflows/e2e.yml`, `conftest.py`, `e2e/Dockerfile`, `e2e/conftest.py` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/23d5b335c2c9e4449e3196ad33a34d94d28520aa) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...23d5b335c2c9e4449e3196ad33a34d94d28520aa) · [Dal](https://github.com/exo-explore/exo/tree/feat/e2e-chaos-tests).


### 109. feat/keep-models-running

Deployment kaydıyla bir modelin çalışır durumda tutulmasını ve uygun düğüm/ağ değiştiğinde yeniden yerleştirilmesini sağlar. Master keeper, API ve kalıcı state türleri eklenir; bir deployment'ın placement hatası diğerlerini durdurmaz.

**Windows katkısı:** Windows veya M1 düğümü kaybolup döndüğünde modeli yeniden ayağa kaldırma hedefi için değerlidir; backend uyumluluğunu ayrıca gerektirir.

**Durum:** 4 ileri / 0 geri; 15 değişen dosya; son commit `286cf0ce`, 2026-10-03T15:00:44+01:00. Açık PR: [#2386](https://github.com/exo-explore/exo/pull/2386) (taslak).

**Kanıt:** Son commit: keeper: a deployment whose placement crashes doesn't stop the others. Dosyalar: `docs/api.md`, `src/exo/api/main.py`, `src/exo/api/tests/test_deployments_api.py`, `src/exo/api/types/__init__.py`, `src/exo/api/types/api.py` ve 10 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/286cf0ce758fd0cf5d71d9af56aa24fe039dccf4) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...286cf0ce758fd0cf5d71d9af56aa24fe039dccf4) · [Dal](https://github.com/exo-explore/exo/tree/feat/keep-models-running).


### 110. feat/mac-studio-rdma-port-warning

Dal adına rağmen görünür değişiklikler RDMA port uyarısından çok prefill ilerleme ve tahminî bitiş süresine yöneliktir. Prefill callback decode yerine giriş işleme akışına bağlanır; API ve progress bar güncellenir.

**Windows katkısı:** Uzun girişlerde Windows/M1 arayüz görünürlüğü fikri yararlıdır; bu dal TB5 veya Windows RDMA desteğinin kanıtı değildir.

**Durum:** 3 ileri / 241 geri; 5 değişen dosya; son commit `23f295e6`, 2026-02-19T07:31:47-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: show ETA on prefill progress bar. Dosyalar: `dashboard/src/lib/components/ChatMessages.svelte`, `dashboard/src/lib/components/PrefillProgressBar.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `src/exo/master/api.py`, `src/exo/worker/engines/mlx/generator/generate.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/23f295e684e2f05ce18086ebab8474cb5c0a8711) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...23f295e684e2f05ce18086ebab8474cb5c0a8711) · [Dal](https://github.com/exo-explore/exo/tree/feat/mac-studio-rdma-port-warning).


### 111. feat/meta-instance-dashboard

MetaInstance nesnelerini dashboard'da yönetmek için panel ekler. ModelCard, ChatSidebar ve ana sayfa/state entegrasyonu değişir; commit eski MlxIbv arayüzünü kaldırdığını da belirtir.

**Windows katkısı:** Küme instance sunumuna ilişkin UI örneğidir; RTX 5070 native Windows runner'ı eklemez.

**Durum:** 1 ileri / 240 geri; 6 değişen dosya; son commit `59b0deb4`, 2026-02-19T09:57:30-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add MetaInstance dashboard UI and remove MlxIbv. Dosyalar: `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/MetaInstancePanel.svelte`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/components/index.ts`, `dashboard/src/lib/stores/app.svelte.ts` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/59b0deb4ab5f67db96c317a860b01ffb5d2f9f94) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...59b0deb4ab5f67db96c317a860b01ffb5d2f9f94) · [Dal](https://github.com/exo-explore/exo/tree/feat/meta-instance-dashboard).


### 112. feat/meta-instance-dashboard-ui

Meta-instance için ayrı MetaInstanceCard bileşeni ve ana sayfa/store bağlantıları ekler. Önceki panel dalından farklı bir dashboard kart uygulamasıdır.

**Windows katkısı:** Windows–M1 instance'larını sunma arayüzüne örnek olabilir; yeni donanım/backend desteği değildir.

**Durum:** 1 ileri / 235 geri; 4 değişen dosya; son commit `b0825335`, 2026-02-19T11:47:23-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: feat: add meta-instance dashboard UI components. Dosyalar: `dashboard/src/lib/components/MetaInstanceCard.svelte`, `dashboard/src/lib/components/index.ts`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/b0825335c7c65a6729b6e98298ffd3b1c77a81ee) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b0825335c7c65a6729b6e98298ffd3b1c77a81ee) · [Dal](https://github.com/exo-explore/exo/tree/feat/meta-instance-dashboard-ui).


### 113. feat/prefill-eta

PrefillProgressBar'a giriş işleme süresinin kalan tahminini ekler. Dashboard state bağlantısıyla birlikte PR için geçici screenshot dosyası da dalda durur.

**Windows katkısı:** Windows ve M1 üzerinde uzun prompt bekleyişini açıklamaya yararlıdır; inference veya bağlantı uyumluluğunu değiştirmez.

**Durum:** 2 ileri / 235 geri; 3 değişen dosya; son commit `340aa368`, 2026-02-19T12:15:44-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: temp: add prefill ETA screenshot for PR. Dosyalar: `dashboard/src/lib/components/PrefillProgressBar.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `prefill-eta-screenshot.png`. [Sabit commit](https://github.com/exo-explore/exo/commit/340aa368773b5cfda491e241af10f900c617e54a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...340aa368773b5cfda491e241af10f900c617e54a) · [Dal](https://github.com/exo-explore/exo/tree/feat/prefill-eta).


### 114. fix/api-closed-stream-errors

Üretim akışı yarıda kapanınca isteğin sessizce kesilmesini veya sonsuza kadar beklemesini önler. API interrupted generation için açık hata döndürür ve cancellation testlerini günceller.

**Windows katkısı:** Windows–M1 kopma testlerinde istemcinin görünür hata alması için yüksek ilgilidir; backend seçimine bağımsız API düzeltmesidir.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `4bdd1a93`, 2026-09-28T02:46:24+01:00. Açık PR: [#2330](https://github.com/exo-explore/exo/pull/2330).

**Kanıt:** Son commit: fix(api): end interrupted generation requests with an explicit error. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_cancel_command.py`, `src/exo/api/tests/test_interrupted_generation_streams.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/4bdd1a93439602cfb0958954669c5c3e578bd5ea) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4bdd1a93439602cfb0958954669c5c3e578bd5ea) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-closed-stream-errors).


### 115. fix/api-event-log-bounded

/events için sınırsız büyüyen günlük yerine yakın geçmiş olaylarını tutan sınırlı tampon kullanır. Görsel verisinin tuttuğu alanı sınırlar, olayları tek cevapta sunar ve Mac hata raporuna ekler.

**Windows katkısı:** Uzun süre çalışan Windows/M1 API düğümlerindeki günlük/bellek büyümesini azaltma açısından ilgilidir; Swift rapor eki Mac tarafına özgüdür.

**Durum:** 3 ileri / 0 geri; 5 değişen dosya; son commit `049ff420`, 2026-09-29T07:42:11+01:00. Açık PR: [#2337](https://github.com/exo-explore/exo/pull/2337).

**Kanıt:** Son commit: fix(api): cap the image data kept for /events. Dosyalar: `app/EXO/EXO/Services/BugReportService.swift`, `docs/api.md`, `src/exo/api/main.py`, `src/exo/api/recent_events.py`, `src/exo/api/tests/test_recent_events.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/049ff4201ac00eea8286eb94f3e9551ed59b247b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...049ff4201ac00eea8286eb94f3e9551ed59b247b) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-event-log-bounded).


### 116. fix/api-image-error-chunk-crash

Görsel üretim hata chunk'ının API düğümünü çökertmesini düzeltir. Hata doğru akışa iletilir ve image error routing testi eklenir.

**Windows katkısı:** Görsel üretim yolu entegre edilirse ortak API kararlılığına yararlıdır; NVIDIA görsel üretim motoru eklemiyor.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `0bbb400e`, 2026-09-28T02:35:10+01:00. Açık PR: [#2331](https://github.com/exo-explore/exo/pull/2331).

**Kanıt:** Son commit: fix(api): forward image generation errors instead of crashing the API. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_image_error_chunk_routing.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/0bbb400e768fb1fba1d67d95de4a6e30e6b3f3f9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0bbb400e768fb1fba1d67d95de4a6e30e6b3f3f9) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-image-error-chunk-crash).


### 117. fix/api-non-stream-errors

Streaming kapalı bir üretim başarısız olduğunda boş HTTP 200 yerine hata cevabı döndürür. Collected response/request logger ayrımı ile istemcinin vazgeçmesini API sunucu hatası gibi kaydetmez.

**Windows katkısı:** Windows ve M1 için aynı OpenAI uyumlu istemci hata sözleşmesini iyileştirir; platformdan bağımsız yüksek ilgi.

**Durum:** 2 ileri / 0 geri; 4 değişen dosya; son commit `ef7ae93d`, 2026-10-01T02:35:34+01:00. Açık PR: [#2356](https://github.com/exo-explore/exo/pull/2356).

**Kanıt:** Son commit: fix(api): a client giving up on a non-streaming request isn't an API error. Dosyalar: `src/exo/api/collected_response.py`, `src/exo/api/main.py`, `src/exo/api/request_logger.py`, `src/exo/api/tests/test_collected_response.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/ef7ae93d7f40e3131de3d573a201f7f42256b9e4) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ef7ae93d7f40e3131de3d573a201f7f42256b9e4) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-non-stream-errors).


### 118. fix/api-place-instance-validates

/place_instance çağrısının kümenin taşıyamadığı yerleşimi kabul etmesini önler. API seviyesinde placement doğrulaması ve kabul/red testleri ekler.

**Windows katkısı:** RTX 5070 VRAM'i ile M1 RAM'i farklı olduğundan yanlış yerleştirmeyi erken reddetme açısından önemlidir; GPU bellek keşfini sağlamaz.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `22d71582`, 2026-09-29T06:09:02+01:00. Açık PR: [#2357](https://github.com/exo-explore/exo/pull/2357).

**Kanıt:** Son commit: fix(api): /place_instance refuses a placement the cluster can't hold. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_place_instance_validation.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/22d71582a08ef630a73f2fde1980b81c0521b524) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...22d71582a08ef630a73f2fde1980b81c0521b524) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-place-instance-validates).


### 119. fix/api-resend-unaccepted-commands

Küme kabul etmediği sohbet komutunu tekrar göndererek sonsuz beklemeyi önler. On saniyelik resend beklemesi ve önceki master'ın kabul ettiği isteği yeniden başlatmayan deduplication eklenir.

**Windows katkısı:** Windows–M1 ağ kopması ve master değişimi senaryolarında istek teslimi için yüksek öncelikli ortak altyapıdır.

**Durum:** 3 ileri / 0 geri; 4 değişen dosya; son commit `db6adf98`, 2026-09-30T17:21:10+01:00. Açık PR: [#2362](https://github.com/exo-explore/exo/pull/2362).

**Kanıt:** Son commit: fix(api): wait 10 s before resending a chat request. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_request_resend.py`, `src/exo/master/main.py`, `src/exo/master/tests/test_repeated_commands.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/db6adf980dd1eb0e2fa7527a3d4fdf5952e1b514) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...db6adf980dd1eb0e2fa7527a3d4fdf5952e1b514) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-resend-unaccepted-commands).


### 120. fix/api-task-finished-on-disconnect

İstemci üretim sırasında ayrılınca API'nin TaskFinished göndermesini sağlar. Böylece master'daki istek görevi tamamlanabilir ve artık istemcinin tutmadığı kayıtlar birikmez.

**Windows katkısı:** Her iki makinede iptal edilen sohbetlerin kaynak tüketimini azaltan cancellation zincirinin API halkasıdır.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `5af3a774`, 2026-09-28T02:37:37+01:00. Açık PR: [#2332](https://github.com/exo-explore/exo/pull/2332).

**Kanıt:** Son commit: fix(api): send TaskFinished when a client disconnects mid-generation. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_task_finished_on_disconnect.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/5af3a7747c9c0b99f3f2491131596dd94493a2cb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5af3a7747c9c0b99f3f2491131596dd94493a2cb) · [Dal](https://github.com/exo-explore/exo/tree/fix/api-task-finished-on-disconnect).


### 121. fix/app-env-var-cancel-crash

Mac uygulamasındaki ortam değişkeni satırlarını liste indeksine değil kimliğe bağlar. Geçersiz isimleri saklamaz/başlatılan sürece iletmez, yapıştırılan satır sonlarını temizler ve tanılanabilir hâle getirir.

**Windows katkısı:** Korunacak M1 Mac uygulamasının ayar güvenilirliğiyle ilgilidir; Windows backend değişkenlerini veya uygulamasını eklemez.

**Durum:** 2 ileri / 0 geri; 5 değişen dosya; son commit `e22fed9d`, 2026-09-28T21:39:52+01:00. Açık PR: [#2343](https://github.com/exo-explore/exo/pull/2343).

**Kanıt:** Son commit: app: name invalid env-var rows, log them at launch, trim pasted newlines. Dosyalar: `app/EXO/EXO/ExoProcessController.swift`, `app/EXO/EXO/Models/CustomEnvironmentVariable.swift`, `app/EXO/EXO/Views/CustomEnvironmentVariableBinding.swift`, `app/EXO/EXO/Views/SettingsView.swift`, `app/EXO/EXOTests/CustomEnvironmentVariableTests.swift`. [Sabit commit](https://github.com/exo-explore/exo/commit/e22fed9df503c1ae9c97dedbdf1b593cc791fd85) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e22fed9df503c1ae9c97dedbdf1b593cc791fd85) · [Dal](https://github.com/exo-explore/exo/tree/fix/app-env-var-cancel-crash).


### 122. fix/app-login-and-browser-settings

Mac uygulamasına oturum açılışında başlatma ve dashboard'u başlangıçta açma tercihleri ekler. İlk login-item kaydı başarısız olursa yeniden dener; startup tercihlerinin yenilenmesi/sıfırlanması testlenir.

**Windows katkısı:** M1 masaüstü deneyimini koruma açısından yararlıdır; Windows oturum açılış entegrasyonunu kapsamıyor.

**Durum:** 2 ileri / 0 geri; 6 değişen dosya; son commit `30cae9fe`, 2026-09-28T21:38:25+01:00. Açık PR: [#2344](https://github.com/exo-explore/exo/pull/2344).

**Kanıt:** Son commit: app: retry a failed first login-item registration; refresh and reset startup settings. Dosyalar: `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/EXOApp.swift`, `app/EXO/EXO/ExoProcessController.swift`, `app/EXO/EXO/Models/StartupPreferences.swift`, `app/EXO/EXO/Views/SettingsView.swift` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/30cae9fea5f422e2fc86b5c8cf7e5ecef9212d94) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...30cae9fea5f422e2fc86b5c8cf7e5ecef9212d94) · [Dal](https://github.com/exo-explore/exo/tree/fix/app-login-and-browser-settings).


### 123. fix/app-networksetup-orphaned-daemon

EXO.app silindikten sonra geride kalan Mac ağ daemon'unu durdurur. Uygulamanın bulunduğu diskin geçici olarak takılı olmaması durumunda daemon'u yanlışlıkla kaldırmaz.

**Windows katkısı:** M1 kurulum/kaldırma yaşam döngüsüne özgüdür; Windows ağ kurulumu için taşınabilir uygulama sunmaz.

**Durum:** 2 ileri / 0 geri; 2 değişen dosya; son commit `9bd9d239`, 2026-09-28T21:36:21+01:00. Açık PR: [#2345](https://github.com/exo-explore/exo/pull/2345) (taslak).

**Kanıt:** Son commit: app: don't remove the network daemon when the app's disk isn't mounted. Dosyalar: `app/EXO/EXO/Services/NetworkSetupHelper.swift`, `app/EXO/EXOTests/NetworkSetupHelperTests.swift`. [Sabit commit](https://github.com/exo-explore/exo/commit/9bd9d2399756d4f9dfa11272dcaff6affad0f89b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9bd9d2399756d4f9dfa11272dcaff6affad0f89b) · [Dal](https://github.com/exo-explore/exo/tree/fix/app-networksetup-orphaned-daemon).


### 124. fix/build-mlx-without-null-this-traps

Nix üzerinden MLX derlemesindeki null-this trap seçeneklerini düzeltir. python/parts.nix değişikliği, açık PR açıklamasına göre MLX >=0.32.1 derlemelerine yöneliktir.

**Windows katkısı:** M1 MLX bağımlılık güncellemesinin derleme kararlılığına yararlıdır; yerel Windows CUDA derleme yolu eklemez.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `344ae0ab`, 2026-10-03T16:43:35+01:00. Açık PR: [#2384](https://github.com/exo-explore/exo/pull/2384).

**Kanıt:** Son commit: fix(build): build MLX without null-`this` traps. Dosyalar: `python/parts.nix`. [Sabit commit](https://github.com/exo-explore/exo/commit/344ae0ab0821b000acc1de4f8ca83f0edcc3c210) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...344ae0ab0821b000acc1de4f8ca83f0edcc3c210) · [Dal](https://github.com/exo-explore/exo/tree/fix/build-mlx-without-null-this-traps).


### 125. fix/custom-model-cards-survive-restart

Kullanıcının eklediği model kartlarının küme yeniden başladığında kaybolmasını düzeltir. Model kartı yönetimi ile worker senkronizasyonu değişir ve restart/sync testi eklenir.

**Windows katkısı:** RTX 5070'ye özgü kartlarla M1 kartlarının korunması için ortak katalog tasarımında ilgilidir; CUDA kart formatı eklemez.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `63b7a2bf`, 2026-09-28T12:54:13+01:00. Açık PR: [#2336](https://github.com/exo-explore/exo/pull/2336).

**Kanıt:** Son commit: fix(worker): keep custom model cards across cluster restarts. Dosyalar: `src/exo/shared/models/model_cards.py`, `src/exo/worker/main.py`, `src/exo/worker/tests/unittests/test_custom_card_sync.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/63b7a2bfde18bb1918cf780a96060cdd46245419) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...63b7a2bfde18bb1918cf780a96060cdd46245419) · [Dal](https://github.com/exo-explore/exo/tree/fix/custom-model-cards-survive-restart).


### 126. fix/dashboard-auto-pick-prefers-downloaded

Otomatik model seçiminde önceden indirilmiş modelleri tercih ederek büyük bir indirmeyi sessizce başlatmayı önler. New Chat mesaj kutusunu bir satır yüksekliğinde tutar; geçici PR screenshot'ları sonradan kaldırılmıştır.

**Windows katkısı:** Windows ve M1 üzerinde gereksiz model indirme/bellek beklentilerini azaltan ortak dashboard iyileştirmesidir.

**Durum:** 4 ileri / 0 geri; 2 değişen dosya; son commit `fcc87f3b`, 2026-09-29T02:04:25+01:00. Açık PR: [#2341](https://github.com/exo-explore/exo/pull/2341).

**Kanıt:** Son commit: fix(dashboard): keep the New Chat message box one line tall. Dosyalar: `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/fcc87f3b12bafbe56391af65b3b598402bed9d31) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...fcc87f3b12bafbe56391af65b3b598402bed9d31) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-auto-pick-prefers-downloaded).


### 127. fix/dashboard-chat-errors

Sohbet stream hatalarını kullanıcıya gösterir ve API hatalarını okunabilir metne dönüştürür. Ortak api_errors yardımcı dosyası ile dashboard store/ana sayfa hata işleme değişir.

**Windows katkısı:** Windows–M1 entegrasyonu sırasında hata teşhisini kolaylaştırır; native Windows inference yeteneği eklemez.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `b618d2d3`, 2026-09-28T00:31:25+01:00. Açık PR: [#2325](https://github.com/exo-explore/exo/pull/2325).

**Kanıt:** Son commit: fix(dashboard): surface chat stream errors and show readable API errors. Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/api_errors.ts`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/b618d2d327ddee57c4f91c7e275dcbfa95a0f966) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b618d2d327ddee57c4f91c7e275dcbfa95a0f966) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-chat-errors).


### 128. fix/dashboard-confirm-model-delete

İndirilmiş modeli silmeden önce onay ister ve silme hatalarını arayüzde görünür kılar. Sohbet/API hata gösterme düzeltmesini de taşır; PR screenshot'ları nihai dal farkından kaldırılmıştır.

**Windows katkısı:** Her iki makinede büyük yerel model dosyalarını yanlış silmeyi azaltır; inference motoruyla ilişkisi dolaylıdır.

**Durum:** 4 ileri / 0 geri; 4 değişen dosya; son commit `667bcde5`, 2026-09-28T20:39:46+01:00. Açık PR: [#2342](https://github.com/exo-explore/exo/pull/2342).

**Kanıt:** Son commit: chore: remove temporary screenshot files. Dosyalar: `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/api_errors.ts`, `dashboard/src/routes/+page.svelte`, `dashboard/src/routes/downloads/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/667bcde5f3da332f582da8c454457b68ceb1e72b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...667bcde5f3da332f582da8c454457b68ceb1e72b) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-confirm-model-delete).


### 129. fix/dashboard-delete-instance-click

Instance silme düğmesine basılınca aynı tıklamanın modeli sohbet için seçmesini engeller. Ana sayfadaki olay akışına dar bir dashboard düzeltmesidir.

**Windows katkısı:** Windows/M1 tarayıcı kullanımında aynı yanlış seçimi önler; backend veya bağlantı desteğini değiştirmez.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `88319023`, 2026-09-28T00:39:00+01:00. Açık PR: [#2324](https://github.com/exo-explore/exo/pull/2324).

**Kanıt:** Son commit: fix(dashboard): don't select a model when deleting its instance. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/88319023bc42314c5e9b787fd1c47e1a1bb5a4c2) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...88319023bc42314c5e9b787fd1c47e1a1bb5a4c2) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-delete-instance-click).


### 130. fix/dashboard-failed-instance-reason

Başarısız instance için yalnız exitcode yerine runner'ın gerçek hata nedenini gösterir. Yeniden denemelerde aynı hatayı tekrar tekrar duyurmak yerine bir kez bildirir.

**Windows katkısı:** Windows CUDA yükleme veya M1 MLX hatasını ayırt etmek için yüksek tanılama ilgisine sahiptir.

**Durum:** 3 ileri / 0 geri; 1 değişen dosya; son commit `e224f13d`, 2026-09-28T21:50:27+01:00. Açık PR: [#2323](https://github.com/exo-explore/exo/pull/2323).

**Kanıt:** Son commit: fix(dashboard): show the runner's error, not "Terminated (exitcode=1", as the failure reason. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/e224f13d23e21ff09c55e95c883d90178ef07d45) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e224f13d23e21ff09c55e95c883d90178ef07d45) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-failed-instance-reason).


### 131. fix/dashboard-instance-lost-notice

Bir cihaz ayrıldığında modelin durduğunu kullanıcıya bildirir. Başarısız instance'ın gerçek hata nedenini gösterme ve tekrar bildirimleri azaltma değişikliklerini de içerir.

**Windows katkısı:** Windows–M1 kümesinde cihaz kopmasını kullanıcıya açıklamak için yararlıdır; modelin otomatik toparlanmasını sağlamaz.

**Durum:** 6 ileri / 0 geri; 3 değişen dosya; son commit `3ba969d8`, 2026-09-28T21:52:09+01:00. Açık PR: [#2340](https://github.com/exo-explore/exo/pull/2340).

**Kanıt:** Son commit: chore: remove temporary screenshot files. Dosyalar: `dashboard/src/lib/components/ToastContainer.svelte`, `dashboard/src/lib/stores/toast.svelte.ts`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/3ba969d82d3b854dc16f5620b2871f67b64d20b0) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3ba969d82d3b854dc16f5620b2871f67b64d20b0) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-instance-lost-notice).


### 132. fix/dashboard-launch-running-model

Çalışmakta olan bir modelin Launch düğmesiyle ikinci kopyasının açılacağını açıkça belirtir. ModelCard ve ana sayfa metin/durum sunumunu düzeltir.

**Windows katkısı:** RTX 5070 VRAM'i ve M1 RAM'inde istemsiz ikinci instance açılmasını önlemeye yardımcı UI değişikliğidir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `d319e6e7`, 2026-09-29T01:23:15+01:00. Açık PR: [#2352](https://github.com/exo-explore/exo/pull/2352).

**Kanıt:** Son commit: fix(dashboard): say when Launch would start a second copy of a model. Dosyalar: `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/d319e6e7cc6aa55b3dbc18adac18b50190e73c48) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...d319e6e7cc6aa55b3dbc18adac18b50190e73c48) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-launch-running-model).


### 133. fix/dashboard-mid-width-layout

768–1023 piksel genişlikteki pencerelerde sohbet arayüzünü kullanılabilir tutar. Sidebar, header ve ana sayfanın orta genişlik düzenini düzeltir.

**Windows katkısı:** Windows ve M1 ekran/pencere düzenine aynı ölçüde yararlıdır; inference davranışını değiştirmez.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `7617fed3`, 2026-09-29T01:34:17+01:00. Açık PR: [#2350](https://github.com/exo-explore/exo/pull/2350).

**Kanıt:** Son commit: fix(dashboard): keep chat usable in 768-1023px wide windows. Dosyalar: `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/HeaderNav.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/7617fed3d0a891f018f7174905c2f48af4311df9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7617fed3d0a891f018f7174905c2f48af4311df9) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-mid-width-layout).


### 134. fix/dashboard-model-search

Model aramasının model adındaki herhangi bir kelimeyle eşleşmesini sağlar. ModelPickerModal içindeki arama filtresine odaklanır.

**Windows katkısı:** Windows/M1 model kataloğunu bulmayı kolaylaştırır; donanım uyumluluk filtresi eklediğine dair kanıt yoktur.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `9b247b46`, 2026-09-29T01:20:42+01:00. Açık PR: [#2351](https://github.com/exo-explore/exo/pull/2351).

**Kanıt:** Son commit: fix(dashboard): make model search find models by any of their words. Dosyalar: `dashboard/src/lib/components/ModelPickerModal.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/9b247b46908f2f94275a90aeb17eb2c4276973cd) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9b247b46908f2f94275a90aeb17eb2c4276973cd) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-model-search).


### 135. fix/dashboard-onboarding-launch-failure

İlk kurulum sırasında model açılamazsa onboarding'in takılı kalmasını önler. Instance hata nedenleri, tekrar bildirimleri ve cihaz ayrılınca modelin durduğunu bildirme düzeltmelerini de taşır.

**Windows katkısı:** Windows NVIDIA yolu ilk kez kurulurken başarısız yükleme akışını görünür kılmak için yararlı UI adayıdır.

**Durum:** 7 ileri / 0 geri; 3 değişen dosya; son commit `55d7362c`, 2026-09-28T21:52:19+01:00. Açık PR: [#2338](https://github.com/exo-explore/exo/pull/2338).

**Kanıt:** Son commit: chore: remove temporary screenshot files. Dosyalar: `dashboard/src/lib/components/ToastContainer.svelte`, `dashboard/src/lib/stores/toast.svelte.ts`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/55d7362c5091613f925abdd534b2dd24a709723a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...55d7362c5091613f925abdd534b2dd24a709723a) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-onboarding-launch-failure).


### 136. fix/dashboard-placement-failure-reason

Model yerleştirilemediğinde gerçek nedeni ve işe yarayabilecek ayarları gösterir. Daha açık bellek hatası biçimini tanıyacak şekilde UI hata sınıflandırmasını günceller.

**Windows katkısı:** RTX 5070 VRAM sınırı ile M1 kaynaklarını ayırt eden yerleştirme tanısı için ilgilidir; donanım ölçümü eklemez.

**Durum:** 4 ileri / 0 geri; 1 değişen dosya; son commit `af82641b`, 2026-10-03T14:40:30+01:00. Açık PR: [#2339](https://github.com/exo-explore/exo/pull/2339).

**Kanıt:** Son commit: dashboard: also recognise the clearer placement memory error. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/af82641baec69cb8fdb5e0a44f12965bc937e535) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...af82641baec69cb8fdb5e0a44f12965bc937e535) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-placement-failure-reason).


### 137. fix/dashboard-recommendation-card-downloads

New Chat öneri kartlarında indirme durumunu gösterir ve büyük indirmelerden önce kullanıcıya sorar. Otomatik seçimde indirilen modeli tercih etme ve tek satırlı mesaj kutusu değişikliklerini de içerir.

**Windows katkısı:** Her iki makinede model indirme davranışını anlaşılır kılar; Windows CUDA model formatı desteği eklemez.

**Durum:** 5 ileri / 0 geri; 3 değişen dosya; son commit `4bd9ed22`, 2026-09-29T02:04:49+01:00. Açık PR: [#2355](https://github.com/exo-explore/exo/pull/2355).

**Kanıt:** Son commit: fix(dashboard): show download state on New Chat cards and ask before big downloads. Dosyalar: `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/lib/components/ChatModelSelector.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/4bd9ed22390a54a53fbfd0ac71bdae1d9b165b08) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4bd9ed22390a54a53fbfd0ac71bdae1d9b165b08) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-recommendation-card-downloads).


### 138. fix/dashboard-selected-model-hint

Bir model seçildikten sonra mesaj gönderildiğinde ne olacağını arayüzde açıklar. Ana sayfadaki seçili model durumunun kullanıcıya anlatılmasını düzeltir.

**Windows katkısı:** Windows/M1 model seçimi akışında açıklık sağlar; backend desteğini değiştirmez.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `5decf69d`, 2026-09-29T01:27:06+01:00. Açık PR: [#2353](https://github.com/exo-explore/exo/pull/2353).

**Kanıt:** Son commit: fix(dashboard): say what sending does once a model is picked. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/5decf69d2aa40c7e9e9173fd4762fb96bb1049b3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5decf69d2aa40c7e9e9173fd4762fb96bb1049b3) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-selected-model-hint).


### 139. fix/dashboard-send-to-running-model

Model seçilmediğinde sohbeti zaten çalışan modele gönderir. İndirilen modeli önceleyen otomatik seçim ve New Chat kutusu düzeltmeleri de dalda bulunur.

**Windows katkısı:** RTX 5070 veya M1 üzerinde çalışan modeli yeniden kullanarak gereksiz yeni yükleme/indirme riskini azaltır.

**Durum:** 5 ileri / 0 geri; 2 değişen dosya; son commit `a3538275`, 2026-09-29T02:04:49+01:00. Açık PR: [#2354](https://github.com/exo-explore/exo/pull/2354).

**Kanıt:** Son commit: fix(dashboard): send to the running model when none is selected. Dosyalar: `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/a35382755a4c59056de7d50b0076314530186104) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a35382755a4c59056de7d50b0076314530186104) · [Dal](https://github.com/exo-explore/exo/tree/fix/dashboard-send-to-running-model).


### 140. fix/discovery-reconnect-after-stall

Düğüm uzun süre durakladıktan sonra peer keşfinin yeniden çalışmasını sağlar. Son sekiz Hello'ya gelen yanıtları kabul eder, yanıt gönderirken döngüyü bekletmez ve kaçırılan timer tick'lerinin birden patlamasını önler.

**Windows katkısı:** Windows–M1 kümesinde uyku/yoğunluk sonrası yeniden keşif için yüksek önceliklidir; native Windows ağ çalışması ayrıca doğrulanmalıdır.

**Durum:** 2 ileri / 0 geri; 1 değişen dosya; son commit `63521473`, 2026-09-28T02:40:44+01:00. Açık PR: [#2327](https://github.com/exo-explore/exo/pull/2327).

**Kanıt:** Son commit: fix(discovery): rediscover peers reliably after a node stalls. Dosyalar: `rust/networking/src/discovery.rs`. [Sabit commit](https://github.com/exo-explore/exo/commit/63521473ef6a8534764a72291e96eb1016a83430) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...63521473ef6a8534764a72291e96eb1016a83430) · [Dal](https://github.com/exo-explore/exo/tree/fix/discovery-reconnect-after-stall).


### 141. fix/discovery-retry-unreachable

EHOSTUNREACH alan arayüz adresini keşif listesinden kalıcı olarak çıkarmak yerine tekrar dener. Hiç Hello gönderilemiyorsa sınırlı sıklıkta uyarı verir; Mac Local Network izni gecikmesi temel tetikleyicidir.

**Windows katkısı:** M1 ağ izni ve geçici erişilemezlik toparlanması için doğrudan ilgili; Windows keşif yolu için genel tekrar deneme fikri taşınabilir.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `f70c0567`, 2026-09-27T23:20:36+01:00. Açık PR: [#2320](https://github.com/exo-explore/exo/pull/2320).

**Kanıt:** Son commit: fix(discovery): keep retrying addresses that fail to send. Dosyalar: `rust/networking/src/discovery.rs`. [Sabit commit](https://github.com/exo-explore/exo/commit/f70c0567ed4d6301119b830e4668675ccd14633b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f70c0567ed4d6301119b830e4668675ccd14633b) · [Dal](https://github.com/exo-explore/exo/tree/fix/discovery-retry-unreachable).


### 142. fix/discovery-stall-hold-off

Duraklama sonrası eski Zenoh oturumları kapanmadan yeni bağlantı kurulmasını önleyerek kalıcı tek yönlü küme bölünmesini giderir. On saniyelik lease sonrasında 12 saniyelik discovery beklemesi ve arka planda dial ekler; önceki iki discovery düzeltmesini de taşır.

**Windows katkısı:** Windows–M1 uyku/yeniden bağlanma kabulünde en güçlü discovery adayıdır; işletim sistemi desteği ve süreler hedef ağda ayrıca testlenmelidir.

**Durum:** 3 ileri / 0 geri; 3 değişen dosya; son commit `86c263be`, 2026-09-28T14:03:54+01:00. Açık PR: [#2346](https://github.com/exo-explore/exo/pull/2346).

**Kanıt:** Son commit: fix(discovery): after a stall, let stale sessions close before reconnecting. Dosyalar: `rust/networking/Cargo.toml`, `rust/networking/src/discovery.rs`, `rust/networking/src/lib.rs`. [Sabit commit](https://github.com/exo-explore/exo/commit/86c263bec8adfc2b07a3816ce5249124a02b5a13) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...86c263bec8adfc2b07a3816ce5249124a02b5a13) · [Dal](https://github.com/exo-explore/exo/tree/fix/discovery-stall-hold-off).


### 143. fix/download-status-only-on-change

İndirme durumlarını yalnız anlamlı değişiklik olduğunda yeniden duyurarak gereksiz küme olaylarını azaltır. Dashboard indirmeler sayfasının kümedeki bütün düğümleri göstermesini de düzeltir.

**Windows katkısı:** Windows ve M1 çoklu düğüm durum görünürlüğü ve event yükü için yararlıdır; yeni indirme/backend desteği eklemez.

**Durum:** 2 ileri / 0 geri; 3 değişen dosya; son commit `01a01ca6`, 2026-09-28T01:12:20+01:00. Açık PR: [#2321](https://github.com/exo-explore/exo/pull/2321).

**Kanıt:** Son commit: fix(dashboard): show every cluster node on the downloads page. Dosyalar: `dashboard/src/routes/downloads/+page.svelte`, `src/exo/download/coordinator.py`, `src/exo/download/tests/test_rescan_announcements.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/01a01ca6d5ca48323e8308d1d4ca9346516a0fc0) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...01a01ca6d5ca48323e8308d1d4ca9346516a0fc0) · [Dal](https://github.com/exo-explore/exo/tree/fix/download-status-only-on-change).


### 144. fix/election-heartbeat

Master heartbeat ile sessiz kalan liderin yerine seçim yapılmasını ve bölünmüş kümelerin yeniden yakınsamasını sağlar. Tek yönlü bağlantının kümeyi sürekli seçim hâlinde tutmasını da ele alır.

**Windows katkısı:** Windows–M1 bağlantı kopması/uyku senaryolarında lider sürekliliği için yüksek öncelikli ortak mantıktır.

**Durum:** 3 ileri / 0 geri; 3 değişen dosya; son commit `a99934f9`, 2026-09-28T13:44:33+01:00. Açık PR: [#2328](https://github.com/exo-explore/exo/pull/2328).

**Kanıt:** Son commit: fix(election): don't let a one-way link keep the cluster in elections. Dosyalar: `src/exo/api/main.py`, `src/exo/shared/election.py`, `src/exo/shared/tests/test_election_heartbeat.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a99934f9afdbe3d5f4761c72fa39b454f4177a4d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a99934f9afdbe3d5f4761c72fa39b454f4177a4d) · [Dal](https://github.com/exo-explore/exo/tree/fix/election-heartbeat).


### 145. fix/election-keep-followed-master

Eski master geri geldiğinde çoğu düğümün izlemekte olduğu master'ı korur. Election kararını gereksiz lider değiştirmeye karşı düzeltir ve mevcut election testlerini günceller.

**Windows katkısı:** Windows veya M1 düğümü dönünce gereksiz küme yeniden düzenlenmesini azaltmak için ilgilidir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `db9eeb3c`, 2026-09-30T15:37:29+01:00. Açık PR: [#2364](https://github.com/exo-explore/exo/pull/2364).

**Kanıt:** Son commit: fix(election): keep the master most nodes follow when the old master returns. Dosyalar: `src/exo/shared/election.py`, `src/exo/shared/tests/test_election.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/db9eeb3c5c17272dc0b4beb1627e12bd4e9a9b4f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...db9eeb3c5c17272dc0b4beb1627e12bd4e9a9b4f) · [Dal](https://github.com/exo-explore/exo/tree/fix/election-keep-followed-master).


### 146. fix/event-log-snapshots

Geç katılan veya geride kalan düğümleri tüm event günlüğünü oynatmak yerine state snapshot ile yakalar. Replay görsel verisine sınır, eski disk günlüğü temizliği ve topolojinin kanonik seri hâle getirilmesi de bulunur.

**Windows katkısı:** Windows–M1 yeniden katılma ve uzun süreli küme çalışmasında event/bellek yükünü azaltan yüksek öncelikli altyapıdır.

**Durum:** 7 ileri / 0 geri; 15 değişen dosya; son commit `9bbb36be`, 2026-09-29T08:57:26+01:00. Açık PR: [#2322](https://github.com/exo-explore/exo/pull/2322).

**Kanıt:** Son commit: fix(types): the worker and the API accept an event receiver with or without snapshots. Dosyalar: `AGENTS.md`, `docs/api.md`, `src/exo/api/main.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 10 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9bbb36be0ca22bf23868e33dba35d13ef55a904f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9bbb36be0ca22bf23868e33dba35d13ef55a904f) · [Dal](https://github.com/exo-explore/exo/tree/fix/event-log-snapshots).


### 147. fix/exo-exits-after-fatal-error

exo durduktan sonra bazı alt bileşenler süreci açık tutsa bile işlemin kapanmasını sağlar. Ana başlangıç/çıkış akışına exit_guard ve test eklenir.

**Windows katkısı:** Yerel Windows süreç kapanışı ve M1 daemon yaşam döngüsü için ilgi taşır; hedef işletim sistemlerinde exit davranışı ayrıca doğrulanmalıdır.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `ebc45b9a`, 2026-10-02T01:34:36+01:00. Açık PR: [#2381](https://github.com/exo-explore/exo/pull/2381).

**Kanıt:** Son commit: fix: exo exits once it has stopped, even if something would hold the process open. Dosyalar: `src/exo/main.py`, `src/exo/utils/exit_guard.py`, `src/exo/utils/tests/test_exit_guard.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/ebc45b9a5f7e49aa7d75f52ce0da320f088682ee) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ebc45b9a5f7e49aa7d75f52ce0da320f088682ee) · [Dal](https://github.com/exo-explore/exo/tree/fix/exo-exits-after-fatal-error).


### 148. fix/fast-synch-only-for-rdma

MLX fast synch seçeneğini yalnız RDMA instance'larında etkinleştirir. Ana süreç ve runner bootstrap değişir; yanlış bağlantı türünde hız senkronizasyonu kullanılmasını testlerle engeller.

**Windows katkısı:** RDMA olmayan M1 bağlantı yolunu korumak için ilgilidir; Windows NVIDIA senkronizasyonuna aynı MLX ayarı uygulanmamalıdır.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `a9ac09ba`, 2026-10-01T17:04:56+01:00. Açık PR: [#2377](https://github.com/exo-explore/exo/pull/2377).

**Kanıt:** Son commit: fix(worker): use MLX fast synch only for RDMA instances. Dosyalar: `src/exo/main.py`, `src/exo/worker/runner/bootstrap.py`, `src/exo/worker/tests/unittests/test_fast_synch.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a9ac09ba25062b625363b3f0b3028a188c4f7d06) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a9ac09ba25062b625363b3f0b3028a188c4f7d06) · [Dal](https://github.com/exo-explore/exo/tree/fix/fast-synch-only-for-rdma).


### 149. fix/honour-namespace-env

EXO_ZENOH_NAMESPACE ortam değişkeninin gerçekten okunmasını sağlar. Aynı ağda farklı kümeleri birbirinden ayırma davranışı README ve namespace testiyle belgelenir.

**Windows katkısı:** Windows–M1 deneme kümesini mevcut Mac kurulumundan izole etmek için doğrudan yararlı ortak ayardır.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `e3ad65fc`, 2026-09-27T22:25:32+01:00. Açık PR: [#2319](https://github.com/exo-explore/exo/pull/2319).

**Kanıt:** Son commit: fix: honour EXO_ZENOH_NAMESPACE for cluster isolation. Dosyalar: `README.md`, `src/exo/main.py`, `src/exo/shared/tests/test_namespace.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/e3ad65fc7ed631eec24a9a015d9fdb7a99b30f3f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e3ad65fc7ed631eec24a9a015d9fdb7a99b30f3f) · [Dal](https://github.com/exo-explore/exo/tree/fix/honour-namespace-env).


### 150. fix/images-travel-with-request

İstek görsellerini istekle birlikte gönderir ve yalnız ihtiyaç sürdükçe tutar. API ve worker planning/forwarding yaşam döngüsü birlikte değişir; görsel kaybı ve gereksiz tutulması testlenir.

**Windows katkısı:** Windows–M1 multimodal istek aktarımında yararlıdır; RTX 5070 için görsel model motoru desteği eklemez.

**Durum:** 2 ileri / 0 geri; 9 değişen dosya; son commit `fe1949b8`, 2026-09-30T13:21:55+01:00. Açık PR: [#2358](https://github.com/exo-explore/exo/pull/2358).

**Kanıt:** Son commit: test: set up the API's task group like the API does. Dosyalar: `src/exo/api/main.py`, `src/exo/api/tests/test_request_images_sent.py`, `src/exo/worker/main.py`, `src/exo/worker/plan.py`, `src/exo/worker/tests/unittests/test_plan/test_download_and_loading.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/fe1949b8c7b1bcdb85d0359bf672f10834bdd2f6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...fe1949b8c7b1bcdb85d0359bf672f10834bdd2f6) · [Dal](https://github.com/exo-explore/exo/tree/fix/images-travel-with-request).


### 151. fix/instance-preview-type-mismatch

/instance/previews uç noktasında beklenen instance türüyle döndürülen tür arasındaki uyuşmazlığı düzeltir. Eski src/exo/master/api.py yapısına tek commitlik API düzeltmesidir.

**Windows katkısı:** Ortak placement önizleme sözleşmesi için fikir sağlar; eski API yolu nedeniyle mevcut Windows–M1 koduna doğrudan uygulanması varsayılamaz.

**Durum:** 1 ileri / 259 geri; 1 değişen dosya; son commit `44845be1`, 2026-02-17T14:51:33-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix instance type mismatch in /instance/previews endpoint. Dosyalar: `src/exo/master/api.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/44845be117fb556217424fc0b2f3c64621df8db9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...44845be117fb556217424fc0b2f3c64621df8db9) · [Dal](https://github.com/exo-explore/exo/tree/fix/instance-preview-type-mismatch).


### 152. fix/instance-retries-count-failed-starts

Instance'tan vazgeçme sınırını ardışık başarısız başlangıçlara göre sayar. Worker'ın geçmişteki başarılı çalışmayı yanlış retry hesabına katmasını engeller ve retry testleri ekler.

**Windows katkısı:** Windows CUDA ve M1 MLX runner'larının geçici yükleme hatalarından toparlanması için ortak worker ilgisi yüksektir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `b5328d78`, 2026-10-03T14:45:14+01:00. Açık PR: [#2387](https://github.com/exo-explore/exo/pull/2387).

**Kanıt:** Son commit: fix(worker): give up on an instance only after failed starts in a row. Dosyalar: `src/exo/worker/main.py`, `src/exo/worker/tests/unittests/test_instance_retries.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/b5328d781e7e60c39fb21754fe3e027032769736) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b5328d781e7e60c39fb21754fe3e027032769736) · [Dal](https://github.com/exo-explore/exo/tree/fix/instance-retries-count-failed-starts).


### 153. fix/keep-models-across-master-change

Master değişince worker/API'yi baştan kurmak yerine mevcut runner'ları ve yüklü modelleri korur. Yeni master snapshot ile state'i devralır; eski master üzerinden yönlenen devam eden istekler yine sonlandırılır.

**Windows katkısı:** Windows–M1 lider değişiminde modelleri yeniden yüklememek için yüksek önceliklidir; devam eden yanıtı kesintisiz sürdürme garantisi değildir.

**Durum:** 8 ileri / 0 geri; 19 değişen dosya; son commit `cd4e53f3`, 2026-10-01T01:26:24+01:00. Açık PR: [#2369](https://github.com/exo-explore/exo/pull/2369).

**Kanıt:** Son commit: fix: keep running models through a change of master. Dosyalar: `AGENTS.md`, `docs/api.md`, `src/exo/api/main.py`, `src/exo/main.py`, `src/exo/master/main.py` ve 14 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/cd4e53f319ba5589b36b0f1a75a9a6a6eae1135f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...cd4e53f319ba5589b36b0f1a75a9a6a6eae1135f) · [Dal](https://github.com/exo-explore/exo/tree/fix/keep-models-across-master-change).


### 154. fix/linear-attention-decode-leak

Qwen3.5 decode sırasında lineer attention cache metadatasının lazy grafiğinin büyüyüp Metal kaynak sınırını aşmasını düzeltir. Her adımda left_padding/lengths dizilerini tokenlarla birlikte değerlendirerek eski grafikleri serbest bırakır.

**Windows katkısı:** Uzun süre yük altında kalan M1 MLX yolu için yüksek önceliklidir; RTX 5070 CUDA bellek sızıntısı düzeltmesi olarak yorumlanmamalıdır.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `34351508`, 2026-10-01T05:30:08+01:00. Açık PR: [#2371](https://github.com/exo-explore/exo/pull/2371).

**Kanıt:** Son commit: fix(mlx): decoding a Qwen3.5 model no longer leaks until the runner crashes. Dosyalar: `.typings/mlx_lm/models/cache.pyi`, `src/exo/worker/engines/mlx/patches/opt_batch_gen.py`, `src/exo/worker/engines/mlx/tests/test_batch_gen_patch.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/34351508c0cfc32d53fa55b4d763e04afbca6919) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...34351508c0cfc32d53fa55b4d763e04afbca6919) · [Dal](https://github.com/exo-explore/exo/tree/fix/linear-attention-decode-leak).


### 155. fix/master-ends-unplaceable-requests

Yerleştirilemeyen bir isteği sessizce düşürmek yerine sonlandırır. Master testleri, uygun model instance'ı bulunamadığında istemcinin beklemede kalmamasını kapsar.

**Windows katkısı:** RTX 5070 VRAM veya M1 RAM yetersizliğinde asılı istekleri önlemek için ortak yüksek ilgi taşır.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `e89cbbc6`, 2026-09-30T14:58:23+01:00. Açık PR: [#2363](https://github.com/exo-explore/exo/pull/2363).

**Kanıt:** Son commit: fix(master): end a request it can't place instead of dropping it. Dosyalar: `src/exo/master/main.py`, `src/exo/master/tests/test_unplaceable_requests.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/e89cbbc6afe571fcb7d39d67bb359e95b8f25f6a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e89cbbc6afe571fcb7d39d67bb359e95b8f25f6a) · [Dal](https://github.com/exo-explore/exo/tree/fix/master-ends-unplaceable-requests).


### 156. fix/master-notices-dead-nodes-sooner

Ölü/donmuş düğümü yaklaşık 15 saniyede fark edecek şekilde master takibini iyileştirir. Master kendi duraklamasını peer hatası saymaz ve duraklama sonrasında peer'lerin bağlanması için ek süre tanır.

**Windows katkısı:** Windows–M1 düğüm kaybını hızlı fakat yanlış pozitif üretmeden algılamak için yüksek önceliklidir.

**Durum:** 3 ileri / 0 geri; 2 değişen dosya; son commit `6947f500`, 2026-09-30T21:18:15+01:00. Açık PR: [#2361](https://github.com/exo-explore/exo/pull/2361).

**Kanıt:** Son commit: fix(master): after its own stall, give nodes time to reconnect too. Dosyalar: `src/exo/master/main.py`, `src/exo/master/tests/test_silent_nodes.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/6947f500614b879ef3e9f3821e629d999efbbb3b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6947f500614b879ef3e9f3821e629d999efbbb3b) · [Dal](https://github.com/exo-explore/exo/tree/fix/master-notices-dead-nodes-sooner).


### 157. fix/model-cards-point-at-existing-repos

İki yerleşik model kartının gerçekten var olan Hugging Face depo adlarına işaret etmesini düzeltir. GLM-4.7 ve Step-3.5-Flash kart adları/bağlantıları ile ilgili benchmark ve cache test referanslarını günceller.

**Windows katkısı:** M1 model indirmelerini düzeltir; bu MLX model kartları RTX 5070 için CUDA formatına dönüşüm sağlamaz.

**Durum:** 1 ileri / 0 geri; 5 değişen dosya; son commit `ec627131`, 2026-10-01T18:53:58+01:00. Açık PR: [#2378](https://github.com/exo-explore/exo/pull/2378).

**Kanıt:** Son commit: fix(models): point two model cards at repositories that exist. Dosyalar: `bench/single-m3-ultra.toml`, `resources/inference_model_cards/mlx-community--GLM-4.7-8bit.toml`, `resources/inference_model_cards/mlx-community--Step-3.5-Flash-8bit.toml`, `src/exo/shared/tests/test_builtin_model_cards.py`, `src/exo/worker/tests/unittests/test_mlx/test_prefix_cache_architectures.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/ec62713128cc16b2346147f03fbbf694f23df45e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ec62713128cc16b2346147f03fbbf694f23df45e) · [Dal](https://github.com/exo-explore/exo/tree/fix/model-cards-point-at-existing-repos).


### 158. fix/model-id-path-safety

Klasör adı olarak kullanılan model kimliklerini doğrular. API, download coordinator ve download yardımcılarında geçersiz model ID'lerinin dosya yolu oluşturmasını engeller.

**Windows katkısı:** Windows sürücü/path semantiğiyle Mac model klasörlerinin güvenli kullanımı için ilgili ortak doğrulamadır; Windows'a özgü bütün kenar durumları burada çalıştırılmadı.

**Durum:** 1 ileri / 0 geri; 5 değişen dosya; son commit `bec975c7`, 2026-09-28T21:37:03+01:00. Açık PR: [#2349](https://github.com/exo-explore/exo/pull/2349).

**Kanıt:** Son commit: fix(download): validate model ids used as folder names. Dosyalar: `src/exo/api/main.py`, `src/exo/download/coordinator.py`, `src/exo/download/download_utils.py`, `src/exo/download/tests/test_model_id_paths.py`, `src/exo/shared/types/common.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/bec975c7fd2c88a2accb9fcda73d2f73e5ce2eed) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...bec975c7fd2c88a2accb9fcda73d2f73e5ce2eed) · [Dal](https://github.com/exo-explore/exo/tree/fix/model-id-path-safety).


### 159. fix/networking-no-silent-drops

Python alıcısına giden ağ kanalını 1024 mesajdan 16384 mesaja çıkarır ve yine oluşan düşüşleri loglar. Kısa alıcı duraklamasının olay sıralarında boşluk ve gecikmiş tekrar aktarım oluşturmasını azaltır.

**Windows katkısı:** Yoğun Windows–M1 kümesinde geçici receive duraklamalarına dayanıklılık için ilgilidir; kayıpsız iletim garantisi değildir.

**Durum:** 1 ileri / 0 geri; 1 değişen dosya; son commit `8177802b`, 2026-09-30T12:17:07+01:00. Açık PR: [#2360](https://github.com/exo-explore/exo/pull/2360).

**Kanıt:** Son commit: fix(networking): don't silently drop incoming messages under load. Dosyalar: `rust/networking/src/swarm.rs`. [Sabit commit](https://github.com/exo-explore/exo/commit/8177802b43783f1fb9a74c107cfa8217139cdac0) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8177802b43783f1fb9a74c107cfa8217139cdac0) · [Dal](https://github.com/exo-explore/exo/tree/fix/networking-no-silent-drops).


### 160. fix/no-downloads-model-loading

--no-downloads seçeneğinin zaten mevcut modellerin yüklenmesini de engellemesini düzeltir. Ana süreç, worker ve planlama yolu indirme ile yükleme izinlerini ayırır.

**Windows katkısı:** İnternetsiz Windows/M1 kabul senaryosunda indirilen modelleri kullanma davranışı için yararlıdır; eski worker yapısına uyarlama gerekir.

**Durum:** 1 ileri / 259 geri; 4 değişen dosya; son commit `ce45af58`, 2026-02-17T14:40:12-08:00. Açık PR: [#1521](https://github.com/exo-explore/exo/pull/1521).

**Kanıt:** Son commit: fix: --no-downloads no longer blocks model loading (#1510). Dosyalar: `src/exo/main.py`, `src/exo/worker/main.py`, `src/exo/worker/plan.py`, `src/exo/worker/tests/unittests/test_plan/test_download_and_loading.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/ce45af58e3d5096c5a4b02cff314bb4edc98fa39) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ce45af58e3d5096c5a4b02cff314bb4edc98fa39) · [Dal](https://github.com/exo-explore/exo/tree/fix/no-downloads-model-loading).


### 161. fix/no-prefill-during-decode-step

Yeni prompt değerlendirmesine başlamadan önce sürmekte olan decode adımının bitmesini bekler. MLX generate ve optimize batch yolunu düzenleyerek tensor-parallel nadir deadlock riskini ele alır.

**Windows katkısı:** M1 MLX tensor-parallel kararlılığı için önemlidir; CUDA–Metal ortak collective veya native Windows deadlock çözümü değildir.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `bc063740`, 2026-10-05T18:30:55+01:00. Açık PR: [#2393](https://github.com/exo-explore/exo/pull/2393).

**Kanıt:** Son commit: fix(mlx): wait for the in-flight decode step before a prompt eval. Dosyalar: `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/engines/mlx/patches/opt_batch_gen.py`, `src/exo/worker/tests/unittests/test_mlx/test_prompt_waits_for_decode_step.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/bc0637406b8069f515f6cf6ac476e6f781ccdf13) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...bc0637406b8069f515f6cf6ac476e6f781ccdf13) · [Dal](https://github.com/exo-explore/exo/tree/fix/no-prefill-during-decode-step).


### 162. fix/pipeline-cancel-deadlock

Pipeline-parallel üretimde iptal edilen sequence'i batch'ten adımlar arasında sökmek yerine bir sonraki normal bitiş adımında tamamlar ve son tokenı atar. Henüz başlamayan iptal edilmiş görevleri kuyruktan kaldırarak sonradan KeyError ile runner çökmesini de önler.

**Windows katkısı:** M1 MLX çoklu düğüm iptal kararlılığı için yüksek önceliklidir; aynı düzeltmenin Windows CUDA engine'e doğrudan uyacağı varsayılamaz.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `7d728477`, 2026-09-30T19:44:46+01:00. Açık PR: [#2365](https://github.com/exo-explore/exo/pull/2365).

**Kanıt:** Son commit: fix(runner): cancelling a request no longer deadlocks a pipeline instance. Dosyalar: `src/exo/worker/engines/mlx/generator/batch_generate.py`, `src/exo/worker/runner/llm_inference/batch_generator.py`, `src/exo/worker/tests/unittests/test_runner/test_batch_cancellation.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/7d728477aa6ae52071434a99551a2c24a9e5e1d8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7d728477aa6ae52071434a99551a2c24a9e5e1d8) · [Dal](https://github.com/exo-explore/exo/tree/fix/pipeline-cancel-deadlock).


### 163. fix/placement-counts-loading-instances

Henüz yüklenmekte olan instance'ın gelecekte tutacağı model payını kullanılmakta olan bellek olarak hesaba katar. Master ve API placement çağrıları runner durumlarını ileterek peş peşe iki yerleştirmenin aynı boş görünen belleği kullanmasını önler.

**Windows katkısı:** RTX 5070 VRAM'i ile M1 belleğinin aşırı tahsisini önlemek için yüksek ilgi taşır; CUDA VRAM bilgisi bu değişiklikten ayrıca sağlanmalıdır.

**Durum:** 1 ileri / 0 geri; 4 değişen dosya; son commit `3b4d3577`, 2026-10-03T14:49:49+01:00. Açık PR: [#2388](https://github.com/exo-explore/exo/pull/2388).

**Kanıt:** Son commit: fix(placement): count the memory of instances that are still loading. Dosyalar: `src/exo/api/main.py`, `src/exo/master/main.py`, `src/exo/master/placement.py`, `src/exo/master/tests/test_placement.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/3b4d357772df0fd89de4619b8b6b8e21d19136f5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3b4d357772df0fd89de4619b8b6b8e21d19136f5) · [Dal](https://github.com/exo-explore/exo/tree/fix/placement-counts-loading-instances).


### 164. fix/prefix-cache-lookup-on-cpu

Prefix cache prompt karşılaştırmasını CPU'ya taşır ve cache'i varsayılan 64 kayıt/RAM'in yüzde 10'u ile sınırlar. Çoklu rank'ta aynı girişlerin korunması için byte bütçesi ve bellek baskısını collective eviction üzerinden uzlaştırır.

**Windows katkısı:** M1 uzun süreli üretimde cache büyümesi ve performans düşüşü için yüksek önceliklidir; Windows CUDA cache yönetimine mimari fikir verir.

**Durum:** 2 ileri / 0 geri; 3 değişen dosya; son commit `a0443857`, 2026-09-30T23:59:23+01:00. Açık PR: [#2368](https://github.com/exo-explore/exo/pull/2368).

**Kanıt:** Son commit: fix(prefix cache): cap it at 64 entries and 10% of RAM. Dosyalar: `.typings/mlx_lm/models/cache.pyi`, `src/exo/worker/engines/mlx/cache.py`, `src/exo/worker/tests/unittests/test_mlx/test_prefix_cache_limits.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a0443857cdf28955679df7dba59460f0267022c2) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a0443857cdf28955679df7dba59460f0267022c2) · [Dal](https://github.com/exo-explore/exo/tree/fix/prefix-cache-lookup-on-cpu).


### 165. fix/rdma-tb5-tooltip

Thunderbolt 5 donanımı görülmediğinde dashboard RDMA instance seçeneğini kapatır. Kullanıcının desteklenmeyen bağlantı tipini seçmesini arayüzde engeller.

**Windows katkısı:** TB5 olmayan M1 yolu için yanlış öneriyi azaltır; RTX 5070 Windows veya M1'e RDMA desteği kazandırmaz.

**Durum:** 1 ileri / 266 geri; 1 değişen dosya; son commit `c84b565a`, 2026-02-17T10:01:24-08:00. Açık PR: [#1505](https://github.com/exo-explore/exo/pull/1505).

**Kanıt:** Son commit: feat: disable RDMA instance type when no Thunderbolt 5 hardware detected. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/c84b565a322141e1813f07c7903d67405b23ddb5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c84b565a322141e1813f07c7903d67405b23ddb5) · [Dal](https://github.com/exo-explore/exo/tree/fix/rdma-tb5-tooltip).


### 166. fix/restart-a-stuck-runner

Üretimin ortasında takılı kalan runner'ı worker supervisor üzerinden yeniden başlatır. Supervisor testleri stuck mid-generation toparlanma davranışını kapsar.

**Windows katkısı:** Windows/M1 worker gözetimi tasarımında yüksek ilgilidir; process/sinyal ayrıntılarının Windows üzerinde ayrıca doğrulanması gerekir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `de996298`, 2026-10-01T00:53:28+01:00. Açık PR: [#2370](https://github.com/exo-explore/exo/pull/2370).

**Kanıt:** Son commit: fix(worker): restart a runner that is stuck mid-generation. Dosyalar: `src/exo/worker/runner/supervisor.py`, `src/exo/worker/tests/unittests/test_runner/test_runner_supervisor.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/de996298c4d04dd7582b032bcba56665310d8330) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...de996298c4d04dd7582b032bcba56665310d8330) · [Dal](https://github.com/exo-explore/exo/tree/fix/restart-a-stuck-runner).


### 167. fix/rotate-log-by-size

exo log dosyasını yalnız program başlangıcında değil boyut sınırına göre döndürür. Uzun süre çalışan süreçte log'un sürekli büyümesini engelleyen ortak logging testi ekler.

**Windows katkısı:** Windows ve M1 uzun süreli kullanımında disk tüketimini sınırlamak için doğrudan yararlıdır.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `310801ba`, 2026-10-04T08:55:19+01:00. Açık PR: [#2390](https://github.com/exo-explore/exo/pull/2390).

**Kanıt:** Son commit: fix(logging): rotate exo's log file by size, not only when exo starts. Dosyalar: `src/exo/shared/logging.py`, `src/exo/shared/tests/test_log_rotation.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/310801ba8a6cdca31cd9c87b8965431593756922) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...310801ba8a6cdca31cd9c87b8965431593756922) · [Dal](https://github.com/exo-explore/exo/tree/fix/rotate-log-by-size).


### 168. fix/router-skip-unheard-messages

Bu düğümde alıcısı olmayan network mesajlarını deserialize etmeden atlar. Topic router ve testleri gereksiz Python parsing maliyetini azaltır.

**Windows katkısı:** Windows–M1 kümesinde CPU/event yükünü azaltan platformdan bağımsız optimizasyon adayıdır.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `07a2209c`, 2026-09-28T14:48:17+01:00. Açık PR: [#2347](https://github.com/exo-explore/exo/pull/2347).

**Kanıt:** Son commit: perf(router): don't parse network messages nothing on this node receives. Dosyalar: `src/exo/routing/router.py`, `src/exo/routing/tests/test_topic_router.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/07a2209cced20aa313d439eaa04d6040cf4ba3e9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...07a2209cced20aa313d439eaa04d6040cf4ba3e9) · [Dal](https://github.com/exo-explore/exo/tree/fix/router-skip-unheard-messages).


### 169. fix/run-mlx-on-one-gpu-stream

Runner'ın model kurma ve üretim dâhil bütün MLX GPU işlerini mlx-lm generation stream üzerinde çalıştırır. Builder/generate/utils ve stream testi, farklı stream'lerin tensor-parallel fast synch ile duraklamasını ele alır.

**Windows katkısı:** M1 MLX yolunu korumak için önemlidir; NVIDIA CUDA stream modeline otomatik aktarılmamalıdır.

**Durum:** 1 ileri / 0 geri; 4 değişen dosya; son commit `be9925ba`, 2026-10-04T13:39:50+01:00. Açık PR: [#2391](https://github.com/exo-explore/exo/pull/2391).

**Kanıt:** Son commit: fix(mlx): run all of a runner's GPU work on mlx-lm's generation stream. Dosyalar: `src/exo/worker/engines/mlx/builder.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/tests/unittests/test_mlx/test_generation_stream.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/be9925ba20606b74fe58558e088bac1d22d2d0cb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...be9925ba20606b74fe58558e088bac1d22d2d0cb) · [Dal](https://github.com/exo-explore/exo/tree/fix/run-mlx-on-one-gpu-stream).


### 170. fix/runner-death-crashes-node

İstekler sürerken runner ölünce bütün node'un da çökmesini önler. Worker supervisor kapanış/hata işleme ve mevcut supervisor testleri düzenlenir.

**Windows katkısı:** RTX 5070 yükleme/üretim hatasının Windows düğümünü veya M1 peer'ini düşürmemesi hedefi açısından yüksek ortak ilgidir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `24d71051`, 2026-10-02T01:15:40+01:00. Açık PR: [#2380](https://github.com/exo-explore/exo/pull/2380).

**Kanıt:** Son commit: fix(worker): a runner dying with requests in flight no longer crashes the node. Dosyalar: `src/exo/worker/runner/supervisor.py`, `src/exo/worker/tests/unittests/test_runner/test_runner_supervisor.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/24d710513b206b4ac246f6ab2eb439fb8e1d4efe) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...24d710513b206b4ac246f6ab2eb439fb8e1d4efe) · [Dal](https://github.com/exo-explore/exo/tree/fix/runner-death-crashes-node).


### 171. fix/runner-stops-when-ring-aborts

Peer bağlantı halkası başarısız olan runner'ı durdurur. Worker supervisor, bağlantısı bozulmuş modelin çalışıyor görünmeye devam etmesini engeller.

**Windows katkısı:** Windows–M1 peer kaybında hızlı temizleme ve yeniden yerleştirme için ilgi taşır; CUDA–Metal ring uyumluluğu eklemez.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `b2fa0d22`, 2026-09-30T22:10:41+01:00. Açık PR: [#2367](https://github.com/exo-explore/exo/pull/2367).

**Kanıt:** Son commit: fix(worker): stop a runner whose connection to its peers has failed. Dosyalar: `src/exo/worker/runner/supervisor.py`, `src/exo/worker/tests/unittests/test_runner/test_runner_supervisor.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/b2fa0d22ea528230cf6d0c3456773228c9d173df) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b2fa0d22ea528230cf6d0c3456773228c9d173df) · [Dal](https://github.com/exo-explore/exo/tree/fix/runner-stops-when-ring-aborts).


### 172. fix/say-why-placement-fails

Placement başarısızlıklarının hepsini bellek yetersizliği diye açıklamak yerine gerçek nedeni döndürür. Placement mantığı ve testler uyumsuz bağlantı/yerleşim gibi ayrı hataları görünür kılar.

**Windows katkısı:** RTX 5070 VRAM sorunu ile M1 bağlantı/backend kısıtını ayırt etmek için yüksek tanılama ilgisine sahiptir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `a0c6e101`, 2026-10-03T14:39:55+01:00. Açık PR: [#2383](https://github.com/exo-explore/exo/pull/2383).

**Kanıt:** Son commit: fix: say why a placement fails instead of always blaming memory. Dosyalar: `src/exo/master/placement.py`, `src/exo/master/tests/test_placement.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a0c6e10137d103530910cea3aed1124ccb570074) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a0c6e10137d103530910cea3aed1124ccb570074) · [Dal](https://github.com/exo-explore/exo/tree/fix/say-why-placement-fails).


### 173. fix/stalled-peer-blocks-cluster

Okumayı bırakan tek peer'in dolu kuyruğunun tüm swarm event döngüsünü bloklamasını önler. Congestion control dolu peer kuyruğunda düşürme kullanır; election mesajlarına daha yüksek öncelik verir ve üst protokol retry/NACK toparlanmasına dayanır.

**Windows katkısı:** Windows veya M1 uykuya geçtiğinde kalan kümenin kilitlenmemesi için yüksek öncelikli ortak ağ düzeltmesidir.

**Durum:** 1 ileri / 0 geri; 6 değişen dosya; son commit `5f348078`, 2026-09-28T02:03:17+01:00. Açık PR: [#2326](https://github.com/exo-explore/exo/pull/2326).

**Kanıt:** Son commit: fix(networking): don't let one stalled peer block delivery to the whole cluster. Dosyalar: `rust/exo_rs/exo_rs.pyi`, `rust/exo_rs/src/networking.rs`, `rust/networking/src/swarm.rs`, `src/exo/routing/router.py`, `src/exo/routing/tests/test_topic_qos.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/5f34807865c9519a23a58eeeb6f494ce218814bc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5f34807865c9519a23a58eeeb6f494ce218814bc) · [Dal](https://github.com/exo-explore/exo/tree/fix/stalled-peer-blocks-cluster).


### 174. fix/state-drop-finished-lifecycle-tasks

Tamamlanan worker bookkeeping/lifecycle görevlerini state'ten çıkarır. Silinen instance'a ait görevler de temizlenir; uzun süreli state büyümesi azaltılır.

**Windows katkısı:** Windows ve M1 üzerinde model aç/kapat/retry döngülerinde bellek/state birikimini azaltmak için ilgilidir.

**Durum:** 2 ileri / 0 geri; 2 değişen dosya; son commit `3b096495`, 2026-09-28T20:32:53+01:00. Açık PR: [#2334](https://github.com/exo-explore/exo/pull/2334).

**Kanıt:** Son commit: fix(state): drop a deleted instance's bookkeeping tasks. Dosyalar: `src/exo/shared/apply.py`, `src/exo/shared/tests/test_apply/test_apply_task_lifecycle.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/3b0964955583f6901ae8f9d1eea756540a8254a6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3b0964955583f6901ae8f9d1eea756540a8254a6) · [Dal](https://github.com/exo-explore/exo/tree/fix/state-drop-finished-lifecycle-tasks).


### 175. fix/state-forgets-runners-of-deleted-instances

Silinen instance'ın runner kayıtlarının state içinde kalmasını düzeltir. State apply mantığı ve runner deletion testleri, instance yaşam döngüsünü tutarlı tutar.

**Windows katkısı:** Windows–M1 instance silme/yeniden yerleştirme akışlarında eski runner bilgisinin yanlış karar üretmesini önlemek için ilgilidir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `ca8ac3b3`, 2026-10-01T10:53:52+01:00. Açık PR: [#2372](https://github.com/exo-explore/exo/pull/2372).

**Kanıt:** Son commit: fix(state): deleted instances no longer leave their runners behind. Dosyalar: `src/exo/shared/apply.py`, `src/exo/shared/tests/test_apply/test_apply_runner_deleted.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/ca8ac3b3296dd00ffdef84c5a217a70d8ba65349) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ca8ac3b3296dd00ffdef84c5a217a70d8ba65349) · [Dal](https://github.com/exo-explore/exo/tree/fix/state-forgets-runners-of-deleted-instances).


### 176. fix/tb5-detection

Dashboard'un bütün Thunderbolt bağlantılarını TB5 sayıp RDMA önermesini düzeltir. RDMA önerisi yalnız TB5 donanım kanıtına bağlanır.

**Windows katkısı:** TB5 olmayan M1 Mac'te yanlış RDMA önerisini önler; Windows RTX 5070 veya genel Thunderbolt RDMA desteği eklemez.

**Durum:** 1 ileri / 166 geri; 1 değişen dosya; son commit `8155e149`, 2026-03-04T13:32:09-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix(dashboard): only suggest RDMA for TB5 hardware, not all Thunderbolt. Dosyalar: `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/8155e14972069a9d7dfddf2f3b033138a7011bf1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8155e14972069a9d7dfddf2f3b033138a7011bf1) · [Dal](https://github.com/exo-explore/exo/tree/fix/tb5-detection).


### 177. fix/unparsable-tool-call-is-content

Modelin ürettiği tool call parser tarafından okunamıyorsa isteği hata ile kesmek yerine metin içerik olarak döndürür. Model output parser ve tool parsing testleri güncellenir.

**Windows katkısı:** Windows/M1 üzerinde aynı API parser kullanılırsa tool kullanımının dayanıklılığına yararlıdır; model/backend desteği eklemez.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `3f6d566c`, 2026-10-06T03:03:07+01:00. Açık PR: [#2394](https://github.com/exo-explore/exo/pull/2394).

**Kanıt:** Son commit: fix: return a tool call the parser can't read as text instead of failing the request. Dosyalar: `src/exo/worker/runner/llm_inference/model_output_parsers.py`, `src/exo/worker/tests/unittests/test_runner/test_parse_tool_calls.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/3f6d566c7ade1c27678773f71dcd943bbbfedaed) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3f6d566c7ade1c27678773f71dcd943bbbfedaed) · [Dal](https://github.com/exo-explore/exo/tree/fix/unparsable-tool-call-is-content).


### 178. fix/unreadable-message-crashes-node

Runner diagnostics mesajlarının onları alan düğümü çökertmesini düzeltir. Router unreadable message işleme ile diagnostics üretimi birlikte değişir ve bozuk mesaj testleri eklenir.

**Windows katkısı:** Windows ve M1 arasında tanılama mesajı alışverişinin node'u düşürmemesi için ortak kararlılık ilgisi yüksektir.

**Durum:** 1 ileri / 0 geri; 4 değişen dosya; son commit `b3c16ea0`, 2026-09-30T23:07:09+01:00. Açık PR: [#2366](https://github.com/exo-explore/exo/pull/2366).

**Kanıt:** Son commit: fix: runner diagnostics crashed the node that received them. Dosyalar: `src/exo/routing/router.py`, `src/exo/routing/tests/__init__.py`, `src/exo/routing/tests/test_unreadable_messages.py`, `src/exo/worker/runner/diagnostics.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/b3c16ea0fd577d19a9110e843e31994729729678) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b3c16ea0fd577d19a9110e843e31994729729678) · [Dal](https://github.com/exo-explore/exo/tree/fix/unreadable-message-crashes-node).


### 179. fix/worker-asks-once-to-delete

Worker'ın vazgeçtiği instance için tekrar tekrar silme komutu istemesini önler. Instance deletion talebi bir kez gönderilir ve worker testi bunu doğrular.

**Windows katkısı:** Windows/M1 başarısız runner döngülerinde gereksiz event/komut yükünü azaltan ortak düzeltmedir.

**Durum:** 1 ileri / 0 geri; 2 değişen dosya; son commit `903a07ae`, 2026-10-03T14:46:48+01:00. Açık PR: [#2389](https://github.com/exo-explore/exo/pull/2389).

**Kanıt:** Son commit: fix(worker): ask once to delete an instance it gave up on. Dosyalar: `src/exo/worker/main.py`, `src/exo/worker/tests/unittests/test_deletion_request.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/903a07ae880973cf629ff5d7a852dcdb392a3c4d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...903a07ae880973cf629ff5d7a852dcdb392a3c4d) · [Dal](https://github.com/exo-explore/exo/tree/fix/worker-asks-once-to-delete).


### 180. fix/worker-cancel-deleted-generation

Master state'inden kaybolmuş üretim görevini runner'da da iptal eder. API'nin Cancelled→silme geçişi worker'ın 100 ms plan döngüsünden hızlı olduğunda kaybolan iptali yakalar; lifecycle görevlerini etkilemez.

**Windows katkısı:** Windows–M1 istemci kopma testlerinde boşa token üretimini durdurmak için yüksek öncelikli worker düzeltmesidir.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `4bbf095c`, 2026-09-28T04:07:34+01:00. Açık PR: [#2335](https://github.com/exo-explore/exo/pull/2335).

**Kanıt:** Son commit: fix(worker): stop generating once a request's task is gone. Dosyalar: `src/exo/worker/plan.py`, `src/exo/worker/tests/unittests/conftest.py`, `src/exo/worker/tests/unittests/test_plan/test_cancel_deleted_tasks.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/4bbf095c1a5dc05b97fecb1801561f705a28180e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4bbf095c1a5dc05b97fecb1801561f705a28180e) · [Dal](https://github.com/exo-explore/exo/tree/fix/worker-cancel-deleted-generation).


### 181. fix/worker-not-blocked-by-busy-runner

Meşgul runner'ın onayını beklerken worker'ın düğümdeki diğer modelleri bloke etmesini önler. Runner'a hiç iletilememiş görevin pending kaydını da temizleyerek sonradan iptalin durmuş task group üzerinde beklemesini giderir.

**Windows katkısı:** Windows/M1 düğümünde birden çok model varsa yavaş runner'ın tüm node'u durdurmaması için yüksek ortak ilgidir.

**Durum:** 2 ileri / 0 geri; 2 değişen dosya; son commit `7265e9e9`, 2026-09-28T23:14:52+01:00. Açık PR: [#2348](https://github.com/exo-explore/exo/pull/2348).

**Kanıt:** Son commit: fix(worker): don't hold a cancel for a task the runner never received. Dosyalar: `src/exo/worker/runner/supervisor.py`, `src/exo/worker/tests/unittests/test_runner/test_supervisor_acknowledgement.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/7265e9e9165cf503fed2ecb2cedb8dbf0cfa442e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7265e9e9165cf503fed2ecb2cedb8dbf0cfa442e) · [Dal](https://github.com/exo-explore/exo/tree/fix/worker-not-blocked-by-busy-runner).


### 182. fix/worker-resurrects-finished-tasks

Worker'ın master tarafından zaten tamamlanmış/iptal edilmiş görevi yeniden state'e duyurmasını önler. Fake runner supervisor'ın in_progress haritasını taklit edecek şekilde test düzenlenir.

**Windows katkısı:** Windows–M1 cancellation/state eşzamanlamasında hayalet görevleri önlemek için ilgili ortak worker düzeltmesidir.

**Durum:** 2 ileri / 0 geri; 2 değişen dosya; son commit `3a68dbfd`, 2026-09-28T11:53:37+01:00. Açık PR: [#2333](https://github.com/exo-explore/exo/pull/2333).

**Kanıt:** Son commit: test: fake runner mirrors the supervisor's in_progress mapping. Dosyalar: `src/exo/worker/main.py`, `src/exo/worker/tests/unittests/test_plan/test_worker_task_announcements.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/3a68dbfd2f98deb1d0974f616e6b1aa604a2459a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3a68dbfd2f98deb1d0974f616e6b1aa604a2459a) · [Dal](https://github.com/exo-explore/exo/tree/fix/worker-resurrects-finished-tasks).


### 183. fix/1025

Issue #1025 için dashboard model kartı ve topology animasyonlarını kaldırarak GPU arayüz yükünü azaltır. Son main merge commitinde Mac Sparkle Package.resolved çakışma çözümü de bulunur.

**Windows katkısı:** Windows ve M1 tarayıcı arayüzü yükü açısından fikir sağlar; RTX 5070 inference hızını ölçülmüş biçimde artırdığı çıkarılamaz.

**Durum:** 3 ileri / 344 geri; 3 değişen dosya; son commit `87098c69`, 2026-02-03T11:56:00+05:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge main into fix/1025. Dosyalar: `app/EXO/EXO.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/87098c69c15357f4dca02aa82f414c56d4337f23) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...87098c69c15357f4dca02aa82f414c56d4337f23) · [Dal](https://github.com/exo-explore/exo/tree/fix/1025).


### 184. fix-instance-preview-type

/instance/previews API'sindeki instance türü uyuşmazlığını gideren başka bir eski dal varyantıdır. Tek commit yalnız src/exo/master/api.py üzerinde değişiklik taşır.

**Windows katkısı:** Ortak preview sözleşmesine fikir verir; eski master API yapısı güncel Windows–M1 koduna uyarlanmalıdır.

**Durum:** 1 ileri / 203 geri; 1 değişen dosya; son commit `dc900029`, 2026-02-23T18:04:38Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix instance type mismatch in /instance/previews endpoint. Dosyalar: `src/exo/master/api.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/dc9000290b68af81b931f37e2f22de62b1ae4f8a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...dc9000290b68af81b931f37e2f22de62b1ae4f8a) · [Dal](https://github.com/exo-explore/exo/tree/fix-instance-preview-type).


### 185. graduate-image-gen

Görsel üretimini experimental durumundan çıkarıp varsayılan açık hâle getirir. Mac uygulama ekranı/process controller ile ortak feature sabitleri ve model kartı seçimi değişir.

**Windows katkısı:** Korunan M1 görsel üretimi akışıyla ilgilidir; varsayılan bayrak değişikliği RTX 5070 native Windows görsel motoru eklemez.

**Durum:** 1 ileri / 227 geri; 4 değişen dosya; son commit `a4c92575`, 2026-02-20T09:13:34-08:00. Açık PR: [#1571](https://github.com/exo-explore/exo/pull/1571) (taslak).

**Kanıt:** Son commit: feat: graduate image generation to non-experimental (default on). Dosyalar: `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/ExoProcessController.swift`, `src/exo/shared/constants.py`, `src/exo/shared/models/model_cards.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/a4c925751f1812c6c1a262bf2a370a0c9d370978) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a4c925751f1812c6c1a262bf2a370a0c9d370978) · [Dal](https://github.com/exo-explore/exo/tree/graduate-image-gen).


### 186. handle-message-too-large

Router'daki MessageTooLarge hatasını yakalayarak node'un çökmesini önler. Büyük ağ mesajının hata sınırında ele alınmasına tek dosyalık eski bir düzeltmedir.

**Windows katkısı:** Windows–M1 büyük payload/çoklu görsel testleri için davranış örneğidir; güncel router yapısına uyarlama gerekir.

**Durum:** 1 ileri / 260 geri; 1 değişen dosya; son commit `c4d24a24`, 2026-02-17T10:34:22-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Handle MessageTooLarge error in router to prevent node crash. Dosyalar: `src/exo/routing/router.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/c4d24a24e41dce9921de91d611411c089cfab71b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c4d24a24e41dce9921de91d611411c089cfab71b) · [Dal](https://github.com/exo-explore/exo/tree/handle-message-too-large).


### 187. integ/phase2

Ağ, election, snapshot, API hata/iptal, worker yaşam döngüsü, MLX bellek ve dashboard/Mac app fixlerini birlikte sınayan geniş entegrasyon dalıdır. Son commitler farklı PR değişiklikleriyle bozulan testleri uyarlar; görünür 154 bağımsız commit ayrı bir küçük özellik değildir.

**Windows katkısı:** Windows–M1 ortak kararlılık düzeltmelerini topluca incelemek için yararlıdır; toplu dalın kendisi native Windows veya CUDA–Metal birlikte inference kanıtı değildir.

**Durum:** 154 ileri / 0 geri; 117 değişen dosya; son commit `6009893e`, 2026-10-02T20:35:58+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: test: adapt tests that other PRs' changes broke (#2330, #2331, #2332, #2335, #2363). Dosyalar: `.typings/mlx_lm/models/cache.pyi`, `AGENTS.md`, `README.md`, `app/EXO/EXO/ContentView.swift`, `app/EXO/EXO/EXOApp.swift` ve 112 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/6009893ee68da17aedb756f59be5ae68548597c9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...6009893ee68da17aedb756f59be5ae68548597c9) · [Dal](https://github.com/exo-explore/exo/tree/integ/phase2).


### 188. iroh

Eski libp2p networking/discovery/swarm uygulamasını kaldırıp iroh, iroh-gossip, iroh-blobs ve iroh-docs bağımlılıklarını ekleyen geçiş taslağıdır. Dal ucunda networking/src/lib.rs boş; PyO3 networking dosyası ve eski testler de silinir, tamamlanmış yeni taşıma uygulaması görünmez.

**Windows katkısı:** Gelecekte Windows/Mac ağ taşıması araştırmasına konu olabilir; bu boş uygulama yerel Windows desteği veya çalışır küme alternatifi değildir.

**Durum:** 1 ileri / 166 geri; 18 değişen dosya; son commit `9f184de3`, 2026-03-04T18:50:32Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: clean. Dosyalar: `Cargo.lock`, `Cargo.toml`, `rust/exo_pyo3_bindings/Cargo.toml`, `rust/exo_pyo3_bindings/README.md`, `rust/exo_pyo3_bindings/src/allow_threading.rs` ve 13 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9f184de3225a9f7826197b4f0ee48f9790e4d1a8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9f184de3225a9f7826197b4f0ee48f9790e4d1a8) · [Dal](https://github.com/exo-explore/exo/tree/iroh).


### 189. iroh-migration

Rust ağ katmanını iroh tabanlı bağlantı ve kimlik yapısına taşıyan deneysel göç dalıdır. Eski libp2p bağlayıcılarını kaldırıp mDNS örnekleri, yönlendirici ve topoloji akışını değiştirir.

**Windows katkısı:** Windows–Mac keşif ve bağlantı tasarımına fikir verir; doğrudan RTX 5070 veya yerel Windows motoru sağlamaz.

**Durum:** 34 ileri / 520 geri; 67 değişen dosya; son commit `e9cfdee9`, 2025-12-24T19:54:48Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix test. Dosyalar: `Cargo.lock`, `Cargo.toml`, `TODO.md`, `flake.nix`, `pyproject.toml` ve 62 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e9cfdee9b871801cf5379951d8e3d30c5cbae155) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e9cfdee9b871801cf5379951d8e3d30c5cbae155) · [Dal](https://github.com/exo-explore/exo/tree/iroh-migration).


### 190. jaccl-build-fix

Nix ile derlenen MLX/JACCL için Apple SDK paketini depoya alır ve MLX_BUILD_CPU seçeneğini açar. Amaç Apple tarafındaki derleme bağımlılıklarını düzeltmektir.

**Windows katkısı:** M1 Mac derleme yolunu koruma açısından ilgili; Windows CUDA desteğiyle doğrudan bağlantısı yoktur.

**Durum:** 5 ileri / 307 geri; 26 değişen dosya; son commit `ed4ee801`, 2026-02-10T12:29:04Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge branch 'main' into jaccl-build-fix. Dosyalar: `flake.nix`, `nix/apple-sdk/README.md`, `nix/apple-sdk/common/add-core-symbolication.nix`, `nix/apple-sdk/common/derivation-options.nix`, `nix/apple-sdk/common/fetch-sdk.nix` ve 21 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ed4ee8010b00e32107772e902c54d712b2094c99) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ed4ee8010b00e32107772e902c54d712b2094c99) · [Dal](https://github.com/exo-explore/exo/tree/jaccl-build-fix).


### 191. leo/add-cuda-typings

Torch, CUDA ve vLLM modülleri için çok sayıda Python tip tanımı ekler. Çalışma motoru eklemekten çok statik tip denetiminin kapsamını genişletir.

**Windows katkısı:** CUDA kodunun bakımına yarar; tip dosyaları RTX 5070 çalıştırma veya yerel Windows desteği kanıtı değildir.

**Durum:** 1 ileri / 147 geri; 1467 değişen dosya; son commit `1350a409`, 2026-03-12T16:25:48Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: CUDA TYPINGS. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi`, `.cuda_typings/torch/cuda/__init__.pyi` ve 1462 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/1350a409ff46c66f8a31941c5d169e46dd175415) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1350a409ff46c66f8a31941c5d169e46dd175415) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-cuda-typings).


### 192. leo/add-gemma-4-parallelism

Gemma 4 model kartlarını ve MLX paralel bölme uygulamasını ekleyen daldır. Paralellik ekleme/kaldırma denemeleri yanında Gemma 4 bölme testleri ve önbellek değişiklikleri içerir.

**Windows katkısı:** Gemma 4 kullanacak M1 tarafı için ilgili; Windows motoruna taşınabilirlik ayrıca değerlendirilmelidir.

**Durum:** 21 ileri / 94 geri; 45 değişen dosya; son commit `8a16b71b`, 2026-04-08T12:38:21+01:00. Açık PR: [#1857](https://github.com/exo-explore/exo/pull/1857) (taslak).

**Kanıt:** Son commit: Merge branch 'leo/add-gemma-4' into leo/add-gemma-4-parallelism. Dosyalar: `.mlx_typings/mlx/nn/layers/quantized.pyi`, `.mlx_typings/mlx_lm/models/gemma4.pyi`, `.mlx_typings/mlx_lm/models/gemma4_text.pyi`, `.mlx_typings/mlx_lm/tokenizer_utils.pyi`, `resources/inference_model_cards/mlx-community--gemma-4-26b-a4b-it-4bit.toml` ve 40 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/8a16b71b4e9c8b3e347abbb674effbfdc2a39219) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8a16b71b4e9c8b3e347abbb674effbfdc2a39219) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-gemma-4-parallelism).


### 193. leo/add-glm-5

GLM-5 model kartlarını ve MLX bölme/üretim uyarlamalarını ekler. Prefill öncesi bariyer, özel MLX sürümü ve runner kapanış zaman aşımı üzerinde de çalışır.

**Windows katkısı:** GLM-5 ve Mac dağıtık çıkarımına yöneliktir; RTX 5070 yerel Windows çözümü olarak gösterilemez.

**Durum:** 28 ileri / 256 geri; 11 değişen dosya; son commit `ea5fc812`, 2026-02-18T16:06:30Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Address comment. Dosyalar: `.mlx_typings/mlx_lm/models/glm_moe_dsa.pyi`, `nix/mlx.nix`, `resources/inference_model_cards/mlx-community--GLM-5-8bit.toml`, `resources/inference_model_cards/mlx-community--GLM-5-MXFP4-Q8.toml`, `resources/inference_model_cards/mlx-community--GLM-5-bf16.toml` ve 6 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ea5fc8125f0284e9bebcd926d7ba97b22e463dea) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ea5fc8125f0284e9bebcd926d7ba97b22e463dea) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-glm-5).


### 194. leo/add-instance-settings

Düşük bellek durumlarını ele alan çalışmayı ayarlar API'si ve dashboard ayarlar sayfasıyla genişletir. Bellek baskısı eşikleri ve üretim/önbellek davranışı bu ayarlara bağlanır.

**Windows katkısı:** M1 belleğini koruma için güçlü adaydır; CUDA VRAM ve Windows ölçümleri ayrı uyarlama ister.

**Durum:** 8 ileri / 183 geri; 12 değişen dosya; son commit `0955966b`, 2026-02-26T13:49:05Z. Açık PR: [#1627](https://github.com/exo-explore/exo/pull/1627) (taslak).

**Kanıt:** Son commit: Claude-generated settings, no idea if it works. Dosyalar: `.mlx_typings/mlx_lm/models/cache.pyi`, `dashboard/src/lib/components/HeaderNav.svelte`, `dashboard/src/lib/stores/settings.svelte.ts`, `dashboard/src/routes/settings/+page.svelte`, `src/exo/master/api.py` ve 7 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/0955966b2a5e003a83f389266a3e57a57c424e6b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...0955966b2a5e003a83f389266a3e57a57c424e6b) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-instance-settings).


### 195. leo/add-logprobs-to-chatcompletion

ChatCompletion logprobs ve skor üretimi için API, yanıt türleri ve batched scoring akışını genişletir. Ayrıca değerlendirme/benchmark araçları ve pipeline üretim düzenlemeleri biriktiren geniş bir deney dalıdır.

**Windows katkısı:** Karma kümenin API ve ölçüm tarafına fikir verir; yerel Windows CUDA motorunu tek başına sağlamaz.

**Durum:** 105 ileri / 375 geri; 34 değişen dosya; son commit `ddc81385`, 2026-02-03T14:54:54Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: raise exo bench default times. Dosyalar: `bench/__init__.py`, `bench/eval_config.toml`, `bench/exo_bench.py`, `bench/exo_eval.py`, `bench/livecodebench_runner.py` ve 29 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ddc81385fd253e9facf52c9fccdd64e0c5ed9507) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ddc81385fd253e9facf52c9fccdd64e0c5ed9507) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-logprobs-to-chatcompletion).


### 196. leo/add-more-tensor-strategies

MLX tensor bölme stratejilerini özellikle DeepSeek ve Qwen3-Next gibi mimariler için genişletir. Önbellek, seed, tokenizer testleri ve MLX sürüm güncellemesi de aynı dalda bulunur.

**Windows katkısı:** M1 bölme davranışını korumada ilgili; NVIDIA/Windows'a doğrudan uyum sonucuna varılamaz.

**Durum:** 30 ileri / 329 geri; 17 değişen dosya; son commit `2a4cf61f`, 2026-02-06T13:34:15Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: remove unnecessary comments. Dosyalar: `.mlx_typings/mlx/core/__init__.pyi`, `.mlx_typings/mlx/nn/layers/convolution.pyi`, `.mlx_typings/mlx_lm/models/cache.pyi`, `.mlx_typings/mlx_lm/models/deepseek_v3.pyi`, `.mlx_typings/mlx_lm/models/qwen3_next.pyi` ve 12 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/2a4cf61f9f6fa911b48fb6e67ef0942ca8fa44e5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...2a4cf61f9f6fa911b48fb6e67ef0942ca8fa44e5) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-more-tensor-strategies).


### 197. leo/add-tool-calling

ChatCompletion yanıtlarına tool calling akışını ekler. Runner çıktıları, chunk türleri ve API işleme yanında bir exo değerlendirme aracı ekler.

**Windows katkısı:** Her iki cihazın ortak API davranışı için ilgili; donanım ve Windows portu açısından dolaylıdır.

**Durum:** 2 ileri / 458 geri; 7 değişen dosya; son commit `826da951`, 2026-01-16T12:55:43Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add exo eval. Dosyalar: `bench/exo_eval.py`, `pyproject.toml`, `src/exo/master/api.py`, `src/exo/shared/types/chunks.py`, `src/exo/shared/types/worker/runner_response.py` ve 2 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/826da9512df2540930c9cdc2f128389659b377ae) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...826da9512df2540930c9cdc2f128389659b377ae) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-tool-calling).


### 198. leo/add-uneven-sharding

Tensor bölmede düğümlere eşit olmayan paylar vermeyi sağlayan çalışmadır. Placement reddini gevşetir, küçük attention head sayılarını ele alır ve dashboard/benchmark bölme kontrolleri ekler.

**Windows katkısı:** Farklı kapasiteli Windows ve M1 cihazları için kavramsal olarak önemlidir; mevcut uygulama MLX odaklıdır.

**Durum:** 5 ileri / 103 geri; 18 değişen dosya; son commit `03c7b762`, 2026-04-01T16:55:38+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Allow small num_heads. Dosyalar: `.mlx_typings/mlx/nn/layers/distributed.pyi`, `.mlx_typings/mlx_lm/models/switch_layers.pyi`, `bench/exo_bench.py`, `bench/harness.py`, `dashboard/src/routes/+page.svelte` ve 13 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/03c7b7627d4954f265ce9e280245b04c2f609a43) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...03c7b7627d4954f265ce9e280245b04c2f609a43) · [Dal](https://github.com/exo-explore/exo/tree/leo/add-uneven-sharding).


### 199. leo/address-rdma-gpu-locks

RDMA sırasında GPU kilidi ve zaman aşımı sorunlarına özel MLX fork'u kullanır. Runner bootstrap, üretim ve kanal kapanışını düzenleyip Nix derlemesini bu bağımlılığa taşır.

**Windows katkısı:** Mac dağıtık çıkarımının kararlılığı için ilgili; Windows RTX 5070 RDMA desteği anlamına gelmez.

**Durum:** 6 ileri / 284 geri; 8 değişen dosya; son commit `03b1e113`, 2026-02-17T11:38:11Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add to nix flake. Dosyalar: `README.md`, `flake.nix`, `nix/mlx.nix`, `pyproject.toml`, `src/exo/utils/channels.py` ve 3 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/03b1e113002ea741930a973e767d11c98ef41c90) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...03b1e113002ea741930a973e767d11c98ef41c90) · [Dal](https://github.com/exo-explore/exo/tree/leo/address-rdma-gpu-locks).


### 200. leo/atif

İç testler için ATIF trajectory kaydı ve inceleme akışını ekler. API uçları, tool parsing düzenlemeleri ve dashboard karşılaştırma/grafik sayfaları içerir.

**Windows katkısı:** Karma kümede sonuçları izlemeye yarar; Windows GPU çalıştırma yoluna doğrudan etkisi yoktur.

**Durum:** 10 ileri / 72 geri; 13 değişen dosya; son commit `7ca01c5b`, 2026-04-15T18:01:03+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add graph. Dosyalar: `.idea/vcs.xml`, `dashboard/src/lib/components/TrajectoryTrendChart.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/trajectories/+page.svelte`, `dashboard/src/routes/trajectories/[sessionId]/+page.svelte` ve 8 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7ca01c5ba8ce031a8c4818f3cfed0d7922a81c7c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7ca01c5ba8ce031a8c4818f3cfed0d7922a81c7c) · [Dal](https://github.com/exo-explore/exo/tree/leo/atif).


### 201. leo/convert-if-necessary

MLX modeli yüklerken gerekli ağırlık dönüşümlerini bellekte yapmayı dener. convert_in_memory modülü ve FP8 ele alma değişiklikleri yükleme yoluna eklenir.

**Windows katkısı:** Mac model uyumluluğu için ilgili; NVIDIA FP8 veya Windows yükleyici desteği olarak yorumlanmamalıdır.

**Durum:** 2 ileri / 76 geri; 2 değişen dosya; son commit `e81d245f`, 2026-04-14T19:08:09+01:00. Açık PR: [#1892](https://github.com/exo-explore/exo/pull/1892).

**Kanıt:** Son commit: Handle fp8. Dosyalar: `src/exo/worker/engines/mlx/convert_in_memory.py`, `src/exo/worker/engines/mlx/utils_mlx.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/e81d245f8e6a6c6c108b2d8385644491ba9d14e4) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e81d245f8e6a6c6c108b2d8385644491ba9d14e4) · [Dal](https://github.com/exo-explore/exo/tree/leo/convert-if-necessary).


### 202. leo/dgx-spark-integrations

DGX Spark için vLLM motoru, Torch tabanlı KV cache, NVML ölçümü ve dashboard cihaz gösterimini ekler. MLX ile ortak runner arayüzü, warmup ve CUDA/Nix paketlemesi üzerinde geniş entegrasyon çalışmasıdır.

**Windows katkısı:** NVIDIA–Mac tasarımı için öncelikli inceleme kaynağıdır; CUDA bağımlılıkları Linux koşullu ve ortamlar Darwin/Linux aarch64 ile sınırlıdır.

**Durum:** 46 ileri / 139 geri; 77 değişen dosya; son commit `be731d3a`, 2026-03-17T19:05:55Z. Açık PR: [#1705](https://github.com/exo-explore/exo/pull/1705) (taslak).

**Kanıt:** Son commit: Merge main. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/pynvml/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi` ve 72 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/be731d3a851319ac7ea914574292acea515a86be) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...be731d3a851319ac7ea914574292acea515a86be) · [Dal](https://github.com/exo-explore/exo/tree/leo/dgx-spark-integrations).


### 203. leo/disable-serverside-tools

API adaptörlerinde sunucu tarafı araçları devre dışı bırakır. Claude URL işleme düzeltmesi ile uzun logların kısaltılması ve tip güvenliği değişikliklerini de taşır.

**Windows katkısı:** Ortak API davranışını etkiler; Windows veya RTX 5070 motor desteği eklemez.

**Durum:** 6 ileri / 91 geri; 21 değişen dosya; son commit `f78d08df`, 2026-04-10T11:18:31+01:00. Açık PR: [#1864](https://github.com/exo-explore/exo/pull/1864) (taslak).

**Kanıt:** Son commit: Disable server side tools. Dosyalar: `src/exo/api/adapters/chat_completions.py`, `src/exo/api/adapters/claude.py`, `src/exo/api/adapters/ollama.py`, `src/exo/api/adapters/responses.py`, `src/exo/api/main.py` ve 16 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/f78d08dfec96cefa5629c791d86ec20d6bc1ba21) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f78d08dfec96cefa5629c791d86ec20d6bc1ba21) · [Dal](https://github.com/exo-explore/exo/tree/leo/disable-serverside-tools).


### 204. leo/exo-version-compat

Düğümlerin exo sürüm bilgisini ve benchmark uyumluluğunu görünür kılar. Ölçüm metodolojisi, zamanlama metrikleri ve bazı kararsız testlerin düzeltmeleri de kapsamdadır.

**Windows katkısı:** Windows–M1 sürüm uyumunu takip etmek için faydalıdır; farklı motorlar arasında çalışabilirlik garantisi vermez.

**Durum:** 9 ileri / 101 geri; 9 değişen dosya; son commit `18036277`, 2026-04-02T23:33:58+01:00. Açık PR: [#1837](https://github.com/exo-explore/exo/pull/1837) (taslak).

**Kanıt:** Son commit: Sneak in some flaky test fixes. Dosyalar: `bench/METHODOLOGY.md`, `bench/exo_bench.py`, `rust/exo_pyo3_bindings/tests/test_python.py`, `src/exo/shared/apply.py`, `src/exo/shared/types/profiling.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/18036277a379166c80f9102051a0cb52a6150e48) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...18036277a379166c80f9102051a0cb52a6150e48) · [Dal](https://github.com/exo-explore/exo/tree/leo/exo-version-compat).


### 205. leo/fallback-to-hf-mirror

Hugging Face erişimi engellendiğinde ayna uç noktasına düşme mekanizması ekler. İndirme yardımcıları, model kartı erişimi ve API bu uç nokta seçimini kullanır.

**Windows katkısı:** Her iki cihazda model indirmeye dolaylı yarar sağlar; Windows çıkarım desteğiyle ilgili değildir.

**Durum:** 1 ileri / 70 geri; 5 değişen dosya; son commit `bfb7975a`, 2026-04-15T23:04:15+01:00. Açık PR: [#1903](https://github.com/exo-explore/exo/pull/1903) (taslak).

**Kanıt:** Son commit: Fallback to HF mirror as a mitigation for China HF limitation. Dosyalar: `src/exo/api/main.py`, `src/exo/download/download_utils.py`, `src/exo/download/hf_endpoints.py`, `src/exo/download/huggingface_utils.py`, `src/exo/shared/models/model_cards.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/bfb7975ab8ff152c403298d5360c57bd6a03a670) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...bfb7975ab8ff152c403298d5360c57bd6a03a670) · [Dal](https://github.com/exo-explore/exo/tree/leo/fallback-to-hf-mirror).


### 206. leo/fix-hf-mirror

Hugging Face ayna üzerinden model indirme akışını düzeltir. Endpoint kontrolü, dashboard/macOS ayarları ve ayna indirmelerine yönelik testler ekler.

**Windows katkısı:** Windows–Mac model temininde yararlı olabilir; CUDA veya yerel Windows yürütme yolu oluşturmaz.

**Durum:** 1 ileri / 63 geri; 15 değişen dosya; son commit `629d6a84`, 2026-04-19T18:47:14+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Fix hf mirror downloads. Dosyalar: `README.md`, `app/EXO/EXO/ExoProcessController.swift`, `app/EXO/EXO/Views/SettingsView.swift`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 10 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/629d6a847b3b533bcb1026fc3bc4bd6edd2442f0) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...629d6a847b3b533bcb1026fc3bc4bd6edd2442f0) · [Dal](https://github.com/exo-explore/exo/tree/leo/fix-hf-mirror).


### 207. leo/fix-small-pipeline-rdma

Küçük pipeline'larda MLX RDMA iletişimini düzeltmek için deneyler içerir. all_gather yerine send/recv, elle senkronizasyon ve son katman yerleşimi alternatiflerini dener.

**Windows katkısı:** Mac pipeline kararlılığı için incelenebilir; heterojen Windows–M1 aktarımı için doğrulanmış çözüm değildir.

**Durum:** 8 ileri / 419 geri; 2 değişen dosya; son commit `06c7e157`, 2026-01-21T11:54:02Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: try manual synchronization. Dosyalar: `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/utils_mlx.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/06c7e157b99a023014905e5aff06c6219b7a28f4) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...06c7e157b99a023014905e5aff06c6219b7a28f4) · [Dal](https://github.com/exo-explore/exo/tree/leo/fix-small-pipeline-rdma).


### 208. leo/fix-step35flash-parser

Step 3.5 Flash tool çağrısı çıktılarının JSON olarak ayrıştırılmasını düzeltir. Aynı dal MLX güncellemesiyle olay sızıntısı sorununu da ele alır.

**Windows katkısı:** Model/API uyumu için dolaylı ilgili; Windows GPU desteği sağlamaz.

**Durum:** 3 ileri / 195 geri; 3 değişen dosya; son commit `aa788228`, 2026-02-24T19:45:20Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix tool parsing to load json if json. Dosyalar: `nix/mlx.nix`, `src/exo/worker/runner/llm_inference/tool_parsers.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/aa788228bc5b6c402206f0a0239fea69f66feccc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...aa788228bc5b6c402206f0a0239fea69f66feccc) · [Dal](https://github.com/exo-explore/exo/tree/leo/fix-step35flash-parser).


### 209. leo/fix-tp-2-2

TP=2 sonuçlarını düzeltmek için embedding, norm, MoE ve quantized katman bölmelerini değiştirir. Bit düzeyinde karşılaştırma testi ekler ve gereken MLX fork API'si yoksa erken hata üretir.

**Windows katkısı:** M1 tensor paralelliğinde önemli; Linux'ta eksik fork API'sini reddeden kontrol Windows–M1 TP'nin hazır olduğunu göstermez.

**Durum:** 9 ileri / 58 geri; 16 değişen dosya; son commit `13e60c4a`, 2026-04-21T13:06:07-07:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix. Dosyalar: `.mlx_typings/mlx/core/__init__.pyi`, `.mlx_typings/mlx/nn/layers/base.pyi`, `.mlx_typings/mlx/nn/layers/distributed.pyi`, `.mlx_typings/mlx/nn/layers/quantized.pyi`, `.mlx_typings/mlx_lm/models/base.pyi` ve 11 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/13e60c4ab15e4b2537124578e0dc679445217581) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...13e60c4ab15e4b2537124578e0dc679445217581) · [Dal](https://github.com/exo-explore/exo/tree/leo/fix-tp-2-2).


### 210. leo/gguf-maybe

GGUF dosyalarından model dönüştürme ve model kartı desteğini deneysel olarak ekler. Linux/Spark cihaz tanıma, dashboard ve doğrudan USB ağ betikleri de aynı dalda bulunur.

**Windows katkısı:** Model formatı ve heterojen cihaz tanıma için fikir verir; native Windows GGUF/CUDA motoru olduğuna kanıt yoktur.

**Durum:** 6 ileri / 152 geri; 29 değişen dosya; son commit `ce675295`, 2026-03-10T18:32:48Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: vibe coding gguf. Dosyalar: `bench_overnight.sh`, `dashboard/src/lib/components/DeviceIcon.svelte`, `dashboard/src/lib/components/ModelCard.svelte`, `dashboard/src/lib/components/TopologyGraph.svelte`, `resources/inference_model_cards/unsloth--DeepSeek-V3.1-GGUF.toml` ve 24 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ce67529524390d96bbe09e30a26de5f60ae28a39) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ce67529524390d96bbe09e30a26de5f60ae28a39) · [Dal](https://github.com/exo-explore/exo/tree/leo/gguf-maybe).


### 211. leo/handle-low-memory-situations

Bellek baskısını izleyip prefix cache girişlerini tahliye eder ve üretimi bellek tükenmeden durdurmaya çalışır. KV cache için token başına bellek ölçer ve düşük bellek halinde hata chunk'ı döndürür.

**Windows katkısı:** M1 bellek güvenilirliği için yüksek öncelikli; Windows VRAM baskısı aynı ölçümle doğrulanmış değildir.

**Durum:** 7 ileri / 183 geri; 6 değişen dosya; son commit `20ea13f0`, 2026-02-26T13:16:28Z. Açık PR: [#1626](https://github.com/exo-explore/exo/pull/1626) (taslak).

**Kanıt:** Son commit: use memory pressure. Dosyalar: `.mlx_typings/mlx_lm/models/cache.pyi`, `src/exo/shared/types/memory.py`, `src/exo/worker/engines/mlx/cache.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/runner/llm_inference/runner.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/20ea13f0479242e1759807f0a87fd4cc4d5da89c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...20ea13f0479242e1759807f0a87fd4cc4d5da89c) · [Dal](https://github.com/exo-explore/exo/tree/leo/handle-low-memory-situations).


### 212. leo/log-kimi-k25

Kimi K2.5'in MLX otomatik bölme yoluna ek tanılama logları koyar. Amaç model davranışını izlemek ve hata ayıklama verisi toplamaktır.

**Windows katkısı:** M1 üzerinde Kimi sorunlarını incelemeye yarar; Windows veya RTX 5070 desteğine katkısı dolaylıdır.

**Durum:** 3 ileri / 195 geri; 1 değişen dosya; son commit `00fc33f2`, 2026-02-24T12:15:26Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: add some logs for david. Dosyalar: `src/exo/worker/engines/mlx/auto_parallel.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/00fc33f260b5689a5bc964c95188a431944588b7) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...00fc33f260b5689a5bc964c95188a431944588b7) · [Dal](https://github.com/exo-explore/exo/tree/leo/log-kimi-k25).


### 213. leo/mlx-update

MLX bağımlılığını güncelleyip auto_parallel içindeki bazı mx.eval çağrılarını kaldırır. Kilit dosyası ve bölme yolu birlikte değişir.

**Windows katkısı:** Mac yürütme/senkronizasyon davranışını etkiler; yerel Windows uyumluluğu kanıtı değildir.

**Durum:** 2 ileri / 26 geri; 3 değişen dosya; son commit `f9f4ee05`, 2026-05-08T18:51:52+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Remove mx.evals. Dosyalar: `pyproject.toml`, `src/exo/worker/engines/mlx/auto_parallel.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/f9f4ee05755cfdf197a67b5fc8f1ef710e190b2a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f9f4ee05755cfdf197a67b5fc8f1ef710e190b2a) · [Dal](https://github.com/exo-explore/exo/tree/leo/mlx-update).


### 214. leo/no-more-sig-9

Model yükleme zaman aşımı ve sert süreç öldürmelerini azaltmayı amaçlar. Runner supervisor ve MLX temizliğini düzenleyerek daha düzgün kapanış denemeleri yapar.

**Windows katkısı:** M1 düğümünü kararlı tutmada ilgili; SIGKILL odaklı yaklaşım Windows süreç modeline ayrıca uyarlanmalıdır.

**Durum:** 1 ileri / 77 geri; 6 değişen dosya; son commit `1c90aa0f`, 2026-04-14T16:04:57+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: No more model load timeout, no more crazy sigkills, try harder to clean up nicely. Dosyalar: `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/runner/llm_inference/runner.py`, `src/exo/worker/runner/runner_supervisor.py`, `src/exo/worker/tests/unittests/test_mlx/conftest.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/1c90aa0f5feec56f72d273d6e01d5a095ad3a544) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1c90aa0f5feec56f72d273d6e01d5a095ad3a544) · [Dal](https://github.com/exo-explore/exo/tree/leo/no-more-sig-9).


### 215. leo/overlapping-pd

Prefill ve decode görevlerini zaman içinde örtüştürerek aktarım beklemesini azaltmayı dener. Uzak prefill istemcisi/sunucusu, MLX adapter'ı, batch runner ve benchmark değişir.

**Windows katkısı:** Windows GPU prefill–Mac decode tasarımı için fikir verir; bu dalın MLX yolu yerel Windows'la doğrulanmış değildir.

**Durum:** 2 ileri / 37 geri; 11 değişen dosya; son commit `aabec11d`, 2026-04-28T15:19:07+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Fix bench. Dosyalar: `bench/prefill_decode_bench.py`, `src/exo/api/main.py`, `src/exo/shared/constants.py`, `src/exo/worker/engines/mlx/disaggregated/adapter.py`, `src/exo/worker/engines/mlx/disaggregated/client.py` ve 6 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/aabec11d5a0d32fb3e524831695ff7fa55443914) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...aabec11d5a0d32fb3e524831695ff7fa55443914) · [Dal](https://github.com/exo-explore/exo/tree/leo/overlapping-pd).


### 216. leo/prefill-2

Prefill/decode ayrıştırmasını instance bağlantıları, ağ protokolü ve dashboard arayüzüyle ekler. MLX KV cache serileştirme/aktarım adapter'ı ve uçtan uca protokol testleri içerir.

**Windows katkısı:** Karma küme mimarisi için önceliklidir; kodda MLX adapter'ı bulunduğu için RTX 5070 Windows tarafı ayrıca gerekir.

**Durum:** 3 ileri / 44 geri; 46 değişen dosya; son commit `63239806`, 2026-04-27T15:10:05+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add tests. Dosyalar: `dashboard/src/lib/components/HeaderNav.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/lib/utils/model_family.ts`, `dashboard/src/routes/advanced/+page.svelte` ve 41 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/63239806c1d6c5eb1e8811e578e4e496249fdf3c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...63239806c1d6c5eb1e8811e578e4e496249fdf3c) · [Dal](https://github.com/exo-explore/exo/tree/leo/prefill-2).


### 217. leo/prefill-decode-really

DGX/vLLM ile MLX arasında prefill/decode ve KV cache aktarımını deneyen geniş bir daldır. Streaming/batch connector, cache uyum betikleri, büyüyen vLLM cache ve çok sayıda benchmark optimizasyonu içerir.

**Windows katkısı:** NVIDIA–M1 ayrıştırma için çok ilgili; CUDA paketleri Linux koşullu olduğundan native Windows desteği ileri sürülemez.

**Durum:** 61 ileri / 139 geri; 111 değişen dosya; son commit `9ec97250`, 2026-04-27T00:57:28+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Better?. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/pynvml/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi` ve 106 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9ec97250457bcb2bc4c6af111d292d1f1578eed9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9ec97250457bcb2bc4c6af111d292d1f1578eed9) · [Dal](https://github.com/exo-explore/exo/tree/leo/prefill-decode-really).


### 218. leo/prepare-batch-implementation

LLM runner'ı batching uygulamasına hazırlamak için parçalara ayırır. Batch generator, model output parser ve dağıtık görev toplama yardımcılarını çıkarıp görüntü runner'ıyla düzeni yakınlaştırır.

**Windows katkısı:** Motor arayüzü ve M1 batching bakımı için ilgili; Windows motoru eklemez.

**Durum:** 7 ileri / 172 geri; 16 değişen dosya; son commit `3239c55e`, 2026-03-03T14:39:23Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Move mx_all_gather_tasks into utils_mlx. Dosyalar: `rust/exo_pyo3_bindings/tests/test_python.py`, `src/exo/routing/router.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/plan.py` ve 11 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/3239c55e401c90527a2c898cad765b59cc20915d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...3239c55e401c90527a2c898cad765b59cc20915d) · [Dal](https://github.com/exo-explore/exo/tree/leo/prepare-batch-implementation).


### 219. leo/prioritise-thunderbolt-ip-for-ring

MLX ring için Thunderbolt bağlantısına ait IP adreslerini öncelikli seçer. Placement yardımcılarında 169.254 bağlantı-yerel adreslerine dayanan tercih mantığı kullanır.

**Windows katkısı:** Mac ağ yoluna faydalıdır; Windows–M1 Thunderbolt/USB aktarımının kullanılabilir olduğunu tek başına kanıtlamaz.

**Durum:** 2 ileri / 360 geri; 1 değişen dosya; son commit `e9e417d8`, 2026-01-29T19:51:25Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: use 169.254, a little hacky. Dosyalar: `src/exo/master/placement_utils.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/e9e417d8e778ccfda14dfdae9173f9fec42acefe) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e9e417d8e778ccfda14dfdae9173f9fec42acefe) · [Dal](https://github.com/exo-explore/exo/tree/leo/prioritise-thunderbolt-ip-for-ring).


### 220. leo/profile-socket-connection-metrics

Düğümler arası socket bağlantı hızını profil eden yardımcı ekler. Ağ metriklerini topolojiye/API'ye taşır ve küçük chunk/bind portu denemeleri yapar.

**Windows katkısı:** Windows–Mac bağlantı performansını ölçme tasarımına uygundur; Windows uygulaması ayrıca kontrol edilmelidir.

**Durum:** 4 ileri / 354 geri; 9 değişen dosya; son commit `12669cd5`, 2026-01-30T19:27:40Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: size tests.... Dosyalar: `src/exo/main.py`, `src/exo/master/api.py`, `src/exo/master/tests/conftest.py`, `src/exo/master/tests/test_placement.py`, `src/exo/master/tests/test_topology.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/12669cd59f5b16161f3d672fff460cb0e89578f1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...12669cd59f5b16161f3d672fff460cb0e89578f1) · [Dal](https://github.com/exo-explore/exo/tree/leo/profile-socket-connection-metrics).


### 221. leo/promote-embedding-layer

Kimi K2.6 model kartını ekleyip TP=2 için embedding katmanı bölmesini düzenler. Asıl değişiklik MLX auto_parallel ve bağımlılık kilidindedir.

**Windows katkısı:** M1 Kimi tensor paralelliği için ilgili; RTX 5070 yerel Windows yoluna doğrudan katkı yoktur.

**Durum:** 2 ileri / 58 geri; 3 değişen dosya; son commit `325ec613`, 2026-04-21T07:49:26+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Fix TP=2. Dosyalar: `resources/inference_model_cards/moonshotai--Kimi-K2.6.toml`, `src/exo/worker/engines/mlx/auto_parallel.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/325ec6136ad9cb337e19308166750a4710bc4f83) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...325ec6136ad9cb337e19308166750a4710bc4f83) · [Dal](https://github.com/exo-explore/exo/tree/leo/promote-embedding-layer).


### 222. leo/reasoning-proxy

Geçici reasoning proxy ve DeepSeek V4/DSML encoding akışını deneyen daldır. API yönlendirmesi, düşünme parametreleri, model kartları ve MLX üretim/önbellek yamaları birlikte değişir.

**Windows katkısı:** Karma sistemin reasoning API'si için incelenebilir; Windows GPU uyumluluğunu çözmez.

**Durum:** 9 ileri / 45 geri; 85 değişen dosya; son commit `8bc74d2c`, 2026-04-25T16:11:45+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Temporary reasoning proxy just to test. Dosyalar: `.mlx_typings/mlx_lm/generate.pyi`, `.mlx_typings/mlx_lm/models/deepseek_v4.pyi`, `bench/exo_bench.py`, `pyproject.toml`, `resources/inference_model_cards/mlx-community--DeepSeek-V4-Flash.toml` ve 80 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/8bc74d2cea87db22a1d95e6870d75af09b92ddcb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8bc74d2cea87db22a1d95e6870d75af09b92ddcb) · [Dal](https://github.com/exo-explore/exo/tree/leo/reasoning-proxy).


### 223. leo/reduce-log-spam

Tek düğümlü JACCL placement sırasında gereksiz uyarıyı kaldırır. Değişiklik yalnızca placement log davranışına odaklanır.

**Windows katkısı:** M1 kullanımında log gürültüsünü azaltır; Windows/CUDA desteğine etkisi yoktur.

**Durum:** 1 ileri / 419 geri; 1 değişen dosya; son commit `541339aa`, 2026-01-20T18:28:51Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Dont warn on single node jaccl placement. Dosyalar: `src/exo/master/placement.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/541339aae6728efd2333a03984148fe2eecf4713) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...541339aae6728efd2333a03984148fe2eecf4713) · [Dal](https://github.com/exo-explore/exo/tree/leo/reduce-log-spam).


### 224. leo/send-from-last-rank

Pipeline sonucunun son rank'ten gönderilmesini ve MLX dağıtık katman iletişimini düzenler. GPT-OSS sorunları sırasında upstream/özel MLX bağımlılıkları arasında çeşitli denemeler içerir.

**Windows katkısı:** Mac pipeline iletişimi için ilgili; Windows–M1 ortak tensor yürütmesi olarak yorumlanmamalıdır.

**Durum:** 11 ileri / 428 geri; 6 değişen dosya; son commit `2220eeb0`, 2026-01-20T14:49:09Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: No more upstream stuff ig. Dosyalar: `pyproject.toml`, `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/runner/runner.py`, `src/exo/worker/tests/unittests/test_mlx/conftest.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/2220eeb0c25c531c9c898e7f9298de8a2ce04bb2) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...2220eeb0c25c531c9c898e7f9298de8a2ce04bb2) · [Dal](https://github.com/exo-explore/exo/tree/leo/send-from-last-rank).


### 225. leo/small-merge

Nemotron 3 Ultra kartları ve çeşitli dashboard/model kartı düzenlemelerini bir araya getirir. NVML ve sistem donanım bilgisi toplama değişiklikleri de aynı küçük birleştirme dalındadır.

**Windows katkısı:** NVIDIA cihaz görünürlüğü ve model seçimi için ilgili; native Windows motor desteği anlamına gelmez.

**Durum:** 2 ileri / 3 geri; 58 değişen dosya; son commit `afa44f43`, 2026-06-05T11:27:32-07:00. Açık PR: [#2154](https://github.com/exo-explore/exo/pull/2154) (taslak).

**Kanıt:** Son commit: Miscellaneous upstream changes. Dosyalar: `dashboard/src/lib/components/FamilyLogos.svelte`, `dashboard/src/lib/components/FamilySidebar.svelte`, `dashboard/src/lib/components/ModelPickerModal.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 53 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/afa44f43b85b7345b38d9ed3111e0720a086e22a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...afa44f43b85b7345b38d9ed3111e0720a086e22a) · [Dal](https://github.com/exo-explore/exo/tree/leo/small-merge).


### 226. leo/test-branch

Model yükleme ve trust_remote_code davranışını inceleyen test dalıdır. MLX yükleyici, model kartları ve dağıtık test yardımcılarını değiştirip remote-code saldırısını yeniden üretmeye yönelik betik ekler.

**Windows katkısı:** Windows portundaki güven sınırlarına fikir verir; bu raporda betik çalıştırılmadı ve doğrulanmış güvenlik sonucu üretilmedi.

**Durum:** 5 ileri / 200 geri; 5 değişen dosya; son commit `e7ce42af`, 2026-02-23T21:12:00Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: tmp changes - DONT PUSH. Dosyalar: `src/exo/shared/models/model_cards.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `tests/get_all_models_on_cluster.py`, `tests/start_distributed_test.py`, `tmp/test_trust_remote_code_attack.sh`. [Sabit commit](https://github.com/exo-explore/exo/commit/e7ce42afc8ac88b78b69caf9da26d3dc8322fc78) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e7ce42afc8ac88b78b69caf9da26d3dc8322fc78) · [Dal](https://github.com/exo-explore/exo/tree/leo/test-branch).


### 227. leo/test-model-hanging

Model yükleme/üretim takılmalarını tanılamak ve hata durumunu kullanıcıya daha düzgün iletmek için deneyler içerir. MLX/MoE bölme alternatifleri, timeout ve kapalı kanal hata işleme değişiklikleri vardır.

**Windows katkısı:** M1 runner kararlılığına ilgili; Windows süreç/kanal uyumu ayrıca incelenmelidir.

**Durum:** 9 ileri / 453 geri; 11 değişen dosya; son commit `8d6e52bd`, 2026-01-16T19:39:44Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Try wrong shardings. Dosyalar: `bench/exo_bench.py`, `src/exo/main.py`, `src/exo/master/api.py`, `src/exo/master/tests/test_api_error_handling.py`, `src/exo/shared/types/api.py` ve 6 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/8d6e52bdb5ac8619c2aec9875a9dd1a447b693ae) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...8d6e52bdb5ac8619c2aec9875a9dd1a447b693ae) · [Dal](https://github.com/exo-explore/exo/tree/leo/test-model-hanging).


### 228. leo/test-stuff-1

Model katmanlarını tek tek fakat eager biçimde yükleme yaklaşımını dener. MLX yükleyici ve otomatik bölme kodu dışında dar bir kapsamı vardır.

**Windows katkısı:** M1 yükleme belleği/gecikmesi için incelenebilir; CUDA Windows yükleme çözümü değildir.

**Durum:** 2 ileri / 433 geri; 2 değişen dosya; son commit `67deec88`, 2026-01-20T11:30:35Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Test stuff. Dosyalar: `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/utils_mlx.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/67deec88ca1e8c376229a8ec3d7e5ade5e08941a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...67deec88ca1e8c376229a8ec3d7e5ade5e08941a) · [Dal](https://github.com/exo-explore/exo/tree/leo/test-stuff-1).


### 229. leo/thermal-results

Uzun süreli çıkarımda termal davranış ve performans değişimini toplar. Benchmark döngüsü/log/grafikler yanında runner ve olay akışında termal deney düzenlemeleri içerir.

**Windows katkısı:** M1 performansını koruma açısından anlamlıdır; RTX 5070 native Windows performans verisi olduğu varsayılmamalıdır.

**Durum:** 3 ileri / 64 geri; 13 değişen dosya; son commit `a9a701f3`, 2026-04-20T11:11:05+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: More thermal results. Dosyalar: `bench/thermal_20260415_002648/loop.log`, `bench/thermal_20260415_002648/performance_over_time.png`, `bench/thermal_20260416_001141/loop.log`, `bench/thermal_20260416_001141/performance_over_time.png`, `bench/thermal_20260416_165129/loop.log` ve 8 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a9a701f3bfd6777532f8d50b488f24e245c5e28b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a9a701f3bfd6777532f8d50b488f24e245c5e28b) · [Dal](https://github.com/exo-explore/exo/tree/leo/thermal-results).


### 230. leo/tmp-test

Kimi tool calling kimlikleri ve ChatCompletion/Claude/Responses adaptör eşlemelerini düzeltmeyi dener. Üretim ve runner çıktılarında araç çağrısı aktarımını değiştirir.

**Windows katkısı:** Karma sistemin API uyumu için dolaylı ilgili; donanım desteğini değiştirmez.

**Durum:** 5 ileri / 318 geri; 6 değişen dosya; son commit `11f9e2e1`, 2026-02-06T18:44:34Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix chat completions call_. Dosyalar: `src/exo/master/adapters/chat_completions.py`, `src/exo/master/adapters/claude.py`, `src/exo/master/adapters/responses.py`, `src/exo/shared/types/api.py`, `src/exo/worker/engines/mlx/generator/generate.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/11f9e2e1d8e2cb391d1f0bee6244f505868a04d6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...11f9e2e1d8e2cb391d1f0bee6244f505868a04d6) · [Dal](https://github.com/exo-explore/exo/tree/leo/tmp-test).


### 231. leo/try-custom-mlx-branch

Özel MLX fork'u kullanımını ve otomatik bölme/yükleme yolunu dener. Ayrıca macOS yerel ağ izinleri için mesaj ve bekleme düzenlemeleri taşıyan release değişikliklerini içerir.

**Windows katkısı:** M1 uygulama/ağ davranışını koruma için ilgili; Windows CUDA motoru sağlamaz.

**Durum:** 8 ileri / 384 geri; 5 değişen dosya; son commit `e0d79cdf`, 2026-01-26T12:05:28Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Use custom mlx branch. Dosyalar: `app/EXO/EXO/Services/NetworkSetupHelper.swift`, `pyproject.toml`, `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/e0d79cdff6c6fadfaeafbac77b64c2b7def30b9c) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e0d79cdff6c6fadfaeafbac77b64c2b7def30b9c) · [Dal](https://github.com/exo-explore/exo/tree/leo/try-custom-mlx-branch).


### 232. leo/use-sm121-branch

vLLM kaynağını rltakashige/vllm-transformers-sm121 fork'una yönelten DGX/CUDA deney dalıdır. Büyüyen cache, prefix caching, GPT-OSS prompt biçimi ve yükleme ilerlemesi düzenlemeleri içerir.

**Windows katkısı:** NVIDIA yolu için yüksek inceleme önceliği taşır; sm121 adı RTX 5070 uyumluluğu kanıtı değildir ve CUDA ortamı Linux ile sınırlıdır.

**Durum:** 32 ileri / 147 geri; 71 değişen dosya; son commit `01701ca6`, 2026-03-16T17:05:17Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: try using different fork. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi`, `.cuda_typings/torch/cuda/__init__.pyi` ve 66 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/01701ca609f85f5442258ee968ce7eb8199b2abb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...01701ca609f85f5442258ee968ce7eb8199b2abb) · [Dal](https://github.com/exo-explore/exo/tree/leo/use-sm121-branch).


### 233. main

Tüm karşılaştırmaların 21a54c5e SHA'lı upstream temel dalıdır. Mevcut MLX 0.32, macOS fork'u ve Linux aarch64/x86_64 CUDA wheel kaynaklarını tanımlar; kendisine göre farkı yoktur.

**Windows katkısı:** M1 yolunu korumak için referanstır; pyproject ortamları Darwin/Linux olduğundan native Windows desteği kanıtlanmaz.

**Durum:** 0 ileri / 0 geri; 0 değişen dosya; son commit `21a54c5e`, 2026-08-25T18:59:53Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: docs: request the mlx extra in the documented setup commands (#2245). Dosyalar: Bağımsız dosya değişikliği yok. [Sabit commit](https://github.com/exo-explore/exo/commit/21a54c5ea0230a3bec1e1a786d200126c7e34ec6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...21a54c5ea0230a3bec1e1a786d200126c7e34ec6) · [Dal](https://github.com/exo-explore/exo/tree/main).


### 234. merge-attempt

Prefill/decode ve DGX/vLLM entegrasyon çalışmasını yeni main API yerleşimine birleştirmeyi dener. KV cache connector'ları, büyüyen cache, benchmark ve CUDA paketleme değişikliklerini toplar.

**Windows katkısı:** Windows–M1 mimari incelemesi için ilgili; birleşim denemesi native Windows desteği veya çalışırlık doğrulaması değildir.

**Durum:** 63 ileri / 80 geri; 105 değişen dosya; son commit `a618d022`, 2026-04-14T12:45:27+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: more fixes. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/pynvml/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi` ve 100 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a618d0227786eceefa0cf2362242963134cccf02) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a618d0227786eceefa0cf2362242963134cccf02) · [Dal](https://github.com/exo-explore/exo/tree/merge-attempt).


### 235. meta-instance-split/jaccl-sidechannel

JACCL tensor işlemleri için pipe tabanlı SideChannel relay'i çıkarır. Master/worker olayları, bootstrap/supervisor ve MLX yardımcılarını özel pipe-sidechannel fork'una bağlar.

**Windows katkısı:** Mac dağıtık iletişiminin korunmasına ilgili; Windows RTX 5070 aktarım desteği ileri sürülemez.

**Durum:** 2 ileri / 216 geri; 10 değişen dosya; son commit `4a3b45a4`, 2026-02-21T12:51:35-08:00. Açık PR: [#1546](https://github.com/exo-explore/exo/pull/1546).

**Kanıt:** Son commit: fix: point MLX dependency to exo-explore/mlx pipe-sidechannel fork. Dosyalar: `nix/mlx.nix`, `pyproject.toml`, `src/exo/master/main.py`, `src/exo/shared/apply.py`, `src/exo/shared/types/events.py` ve 5 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/4a3b45a43933a414dabdd5740f2ad817f0a2d305) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4a3b45a43933a414dabdd5740f2ad817f0a2d305) · [Dal](https://github.com/exo-explore/exo/tree/meta-instance-split/jaccl-sidechannel).


### 236. new-bridge-script

macOS bridge yapılandırmasını kapatmaya yönelik kill_bridge_plist shell betiği ekler. Uygulama çalışma motorunda değişiklik yapmayan yardımcı deney dalıdır.

**Windows katkısı:** Mac ağ teşhisine dolaylı ilgili; Windows portunda uygulanacak bir betik değildir.

**Durum:** 1 ileri / 428 geri; 1 değişen dosya; son commit `1bca9674`, 2026-01-20T14:03:14Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: add new kill bridge script. Dosyalar: `tmp/kill_bridge_plist.sh`. [Sabit commit](https://github.com/exo-explore/exo/commit/1bca96747d254a2036d5161059b89a3d5e8d23dc) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1bca96747d254a2036d5161059b89a3d5e8d23dc) · [Dal](https://github.com/exo-explore/exo/tree/new-bridge-script).


### 237. nid-persist

Düğüm kimliğinin .cache altında yeniden başlatmalar arasında korunmasını düzenler. Yönlendirici, ortak sabitler ve XDG yol testlerini değiştirir.

**Windows katkısı:** Windows–Mac düğüm kimliği sürekliliği için ilgili; Windows cache yolu uyumu ayrıca doğrulanmalıdır.

**Durum:** 1 ileri / 139 geri; 3 değişen dosya; son commit `74b877db`, 2026-03-18T11:24:04Z. Açık PR: [#1619](https://github.com/exo-explore/exo/pull/1619).

**Kanıt:** Son commit: persist node ids in .cache. Dosyalar: `src/exo/routing/router.py`, `src/exo/shared/constants.py`, `src/exo/shared/tests/test_xdg_paths.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/74b877dbcd1f711f9696c693d24bb599059cc323) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...74b877dbcd1f711f9696c693d24bb599059cc323) · [Dal](https://github.com/exo-explore/exo/tree/nid-persist).


### 238. optimize-dashboard

Dashboard topoloji çizimi, uygulama store'u ve sayfa/CSS akışını optimize eder. Değişiklik kullanıcı arayüzü performansına odaklanır.

**Windows katkısı:** Her iki cihazın küme görünümünü iyileştirebilir; CUDA veya Windows yürütme desteğini değiştirmez.

**Durum:** 1 ileri / 512 geri; 5 değişen dosya; son commit `40cbecb5`, 2025-12-29T22:00:59+05:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: optimize dashboard. Dosyalar: `dashboard/src/app.css`, `dashboard/src/lib/components/TopologyGraph.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+layout.svelte`, `dashboard/src/routes/+page.svelte`. [Sabit commit](https://github.com/exo-explore/exo/commit/40cbecb5c44fde62b22b11e8cb6f341e043d7cf3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...40cbecb5c44fde62b22b11e8cb6f341e043d7cf3) · [Dal](https://github.com/exo-explore/exo/tree/optimize-dashboard).


### 239. perf/reuse-detokenizer

MLX istek başına detokenizer oluşturma işini tekrar kullanarak azaltır. Küçük bir patch modülü ve yeniden kullanım testi ekler; main'in doğrudan üzerine tek commit taşır.

**Windows katkısı:** M1 istek başlatma maliyeti için dar ve güncel adaydır; Windows NVIDIA motoruna doğrudan uygulanmaz.

**Durum:** 1 ileri / 0 geri; 3 değişen dosya; son commit `749034ff`, 2026-10-01T12:05:58+01:00. Açık PR: [#2379](https://github.com/exo-explore/exo/pull/2379).

**Kanıt:** Son commit: perf(mlx): build a tokenizer's detokenizer once, not twice per request. Dosyalar: `src/exo/worker/engines/mlx/patches/__init__.py`, `src/exo/worker/engines/mlx/patches/reuse_detokenizer.py`, `src/exo/worker/engines/mlx/tests/test_reuse_detokenizer.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/749034ff8cd48da655f29b58fc38230e145a11a5) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...749034ff8cd48da655f29b58fc38230e145a11a5) · [Dal](https://github.com/exo-explore/exo/tree/perf/reuse-detokenizer).


### 240. pipeline-dependency-graph

MLX dağıtık işlemleri arasında açık bağımlılık kenarları ekler. Pipeline katmanları, KV cache ve batch/tekli üretim akışında sıralamayı düzenleyip MLX bağımlılığını günceller.

**Windows katkısı:** M1 pipeline senkronizasyonunu korumada önceliklidir; Windows–Mac aktarımının hazır olduğunu göstermez.

**Durum:** 3 ileri / 19 geri; 6 değişen dosya; son commit `81b5599e`, 2026-05-12T12:53:13+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Bump mlx. Dosyalar: `src/exo/worker/engines/mlx/auto_parallel.py`, `src/exo/worker/engines/mlx/cache.py`, `src/exo/worker/engines/mlx/generator/batch_generate.py`, `src/exo/worker/engines/mlx/generator/generate.py`, `src/exo/worker/tests/unittests/test_mlx/test_auto_parallel.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/81b5599e4320577b65282fa04132df32096753c6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...81b5599e4320577b65282fa04132df32096753c6) · [Dal](https://github.com/exo-explore/exo/tree/pipeline-dependency-graph).


### 241. prefix-cache-oom

Uzayan hybrid model context'inde prefix cache snapshot birikimini sınırlar. Token konumuna göre tekrarları ayıklayıp en yeni 16 snapshot'ı saklar ve en güncel geri dönüş noktasını seçer.

**Windows katkısı:** M1 bellek korunması için güçlü adaydır; Windows VRAM yolu aynı MLX cache yapısını kullanıyorsa ayrıca değerlendirilir.

**Durum:** 2 ileri / 5 geri; 2 değişen dosya; son commit `91a9d0e1`, 2026-06-02T12:09:28-07:00. Açık PR: [#2137](https://github.com/exo-explore/exo/pull/2137).

**Kanıt:** Son commit: Use sliding window. Dosyalar: `src/exo/worker/engines/mlx/cache.py`, `src/exo/worker/tests/unittests/test_mlx/test_kv_prefix_cache.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/91a9d0e10e894d3af41f5706cb0db42fc3b0345b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...91a9d0e10e894d3af41f5706cb0db42fc3b0345b) · [Dal](https://github.com/exo-explore/exo/tree/prefix-cache-oom).


### 242. releases/v1.0.65

v1.0.65 için macOS ağ kurulumunu ve MLX yükleme/bağımlılık değişikliklerini taşıyan release dalıdır. Ağ izni mesajını iyileştirir ve kurulumun tamamlanması için bekleme ekler.

**Windows katkısı:** M1 uygulama davranışının tarihsel referansıdır; güncel native Windows desteği içerdiği söylenemez.

**Durum:** 10 ileri / 376 geri; 4 değişen dosya; son commit `4f24e33d`, 2026-01-26T14:01:15-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge branch 'main' into releases/v1.0.65. Dosyalar: `app/EXO/EXO/Services/NetworkSetupHelper.swift`, `pyproject.toml`, `src/exo/worker/engines/mlx/utils_mlx.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/4f24e33d3006c2c3df56ab50140c15353dd322c4) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4f24e33d3006c2c3df56ab50140c15353dd322c4) · [Dal](https://github.com/exo-explore/exo/tree/releases/v1.0.65).


### 243. releases/v1.0.66

v1.0.66 release dalı önceki macOS ağ kurulum düzeltmelerini taşır. Ayrıca KV prefix cache düzeltmesini geri alarak önbellek, üretim ve test dosyalarını değiştirir.

**Windows katkısı:** Mac önbellek regresyonlarının tarihini anlamaya yarar; Windows portuna topluca taşımak için hazır aday değildir.

**Durum:** 11 ileri / 376 geri; 10 değişen dosya; son commit `9ce0d460`, 2026-01-26T14:07:15-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Revert "Fix kv prefix cache (#1262)". Dosyalar: `app/EXO/EXO/Services/NetworkSetupHelper.swift`, `pyproject.toml`, `src/exo/shared/types/mlx.py`, `src/exo/worker/engines/mlx/cache.py`, `src/exo/worker/engines/mlx/constants.py` ve 5 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9ce0d4602d793b1288b03801548e5b931add2532) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9ce0d4602d793b1288b03801548e5b931add2532) · [Dal](https://github.com/exo-explore/exo/tree/releases/v1.0.66).


### 244. releases/v1.0.67

v1.0.67 release dalı macOS ağ kurulum mesajı/bekleme ve MLX bağımlılık/yükleme düzenlemelerini taşır. Birçok main birleştirmesi nedeniyle bağımsız yeni özellik dalı gibi değerlendirilmemelidir.

**Windows katkısı:** M1 release davranışı için tarihsel bilgi verir; Windows RTX 5070 çalıştırma kanıtı yoktur.

**Durum:** 11 ileri / 373 geri; 4 değişen dosya; son commit `b9c64f94`, 2026-01-27T22:29:07-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Merge remote-tracking branch 'origin/main' into releases/v1.0.67. Dosyalar: `app/EXO/EXO/Services/NetworkSetupHelper.swift`, `pyproject.toml`, `src/exo/worker/engines/mlx/utils_mlx.py`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/b9c64f94d0ae2607135e4c2d9bb2eac9cd841840) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b9c64f94d0ae2607135e4c2d9bb2eac9cd841840) · [Dal](https://github.com/exo-explore/exo/tree/releases/v1.0.67).


### 245. remove-custom-discovery

Özel Rust keşif/swarm yapısını sadeleştirip mDNS süresi dolduğunda bağlantıyı kesmeyi düzenler. Eski wakerdeque ve yardımcı Rust crate'lerini kaldırır.

**Windows katkısı:** Windows–Mac keşif yaşam döngüsüne fikir verir; yeni GPU backend'i eklemez.

**Durum:** 6 ileri / 166 geri; 12 değişen dosya; son commit `69a084cf`, 2026-03-04T18:55:21Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: disconnect on mdns expiry. Dosyalar: `Cargo.lock`, `Cargo.toml`, `rust/exo_pyo3_bindings/Cargo.toml`, `rust/exo_pyo3_bindings/src/networking.rs`, `rust/networking/Cargo.toml` ve 7 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/69a084cf975b80f9602e0b7f1aac689dd44d1fd1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...69a084cf975b80f9602e0b7f1aac689dd44d1fd1) · [Dal](https://github.com/exo-explore/exo/tree/remove-custom-discovery).


### 246. revert-1906-leo/update-mlx-3

1906 numaralı MLX ve mlx-lm güncellemesini geri alır. Nix MLX tanımı ve kilit dosyasıyla önceki bağımlılık setine dönüşü hedefler.

**Windows katkısı:** Mac bağımlılık regresyonlarını araştırmak için ilgili; native Windows desteği ekleyen değişiklik değildir.

**Durum:** 1 ileri / 68 geri; 2 değişen dosya; son commit `c4936c12`, 2026-04-16T21:33:46+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Revert "Update mlx and mlx lm to latest (#1906)". Dosyalar: `nix/mlx.nix`, `uv.lock`. [Sabit commit](https://github.com/exo-explore/exo/commit/c4936c124d3079ed6ba319c2da154a78658c2876) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c4936c124d3079ed6ba319c2da154a78658c2876) · [Dal](https://github.com/exo-explore/exo/tree/revert-1906-leo/update-mlx-3).


### 247. runner-opts

Runner seçeneklerini merkezi bir RunnerOpts yapısına taşır. --trust-remote-code seçeneğini ana girişten worker/runner ve MLX yükleyiciye aktarır.

**Windows katkısı:** Windows portunda seçeneklerin tutarlı taşınması için ilgili; güven seçeneği donanım uyumluluğu sağlamaz.

**Durum:** 1 ileri / 173 geri; 9 değişen dosya; son commit `5087674b`, 2026-03-03T10:49:42Z. Açık PR: [#1635](https://github.com/exo-explore/exo/pull/1635) (taslak).

**Kanıt:** Son commit: runner opts. Dosyalar: `src/exo/main.py`, `src/exo/worker/engines/mlx/utils_mlx.py`, `src/exo/worker/main.py`, `src/exo/worker/runner/bootstrap.py`, `src/exo/worker/runner/image_models/runner.py` ve 4 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/5087674b604ff3e63660dc9c4ec34dc4e751a23b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5087674b604ff3e63660dc9c4ec34dc4e751a23b) · [Dal](https://github.com/exo-explore/exo/tree/runner-opts).


### 248. runner-refactor

Runner/engine yapısını exo_core, mlx_engine ve vllm_engine Python paketlerine ayıran büyük bir refaktördür. Model tipleri, tokenizer/parser ve cache sorumluluklarını ortak arayüz etrafında taşıyıp vLLM yükleme denemeleri içerir.

**Windows katkısı:** Windows CUDA motorunu Mac MLX'ten ayırma tasarımı için önemlidir; mevcut kodun native Windows'ta çalıştığı kanıtlanmamıştır.

**Durum:** 58 ileri / 139 geri; 469 değişen dosya; son commit `fd17a3bc`, 2026-03-27T12:02:36Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: vllm loads!. Dosyalar: `.cuda_typings/openai_harmony/__init__.pyi`, `.cuda_typings/pynvml/__init__.pyi`, `.cuda_typings/torch/__init__.pyi`, `.cuda_typings/torch/backends/__init__.pyi`, `.cuda_typings/torch/backends/cuda/__init__.pyi` ve 464 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/fd17a3bc09993917e2616684594479dfab20106e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...fd17a3bc09993917e2616684594479dfab20106e) · [Dal](https://github.com/exo-explore/exo/tree/runner-refactor).


### 249. runner-refactor-2

MLX ve MFlux için ortak engine arayüzü ve builder yapıları uygular. Metin/görüntü runner ayrımını ortak runner/supervisor akışına taşır.

**Windows katkısı:** M1 motorunu koruyarak ikinci backend eklemek için mimari adaydır; Windows CUDA motoru kendiliğinden oluşmaz.

**Durum:** 1 ileri / 45 geri; 20 değişen dosya; son commit `4216ca54`, 2026-04-25T01:52:29+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: implement engine interface for mlx and mflux. Dosyalar: `src/exo/shared/types/chunks.py`, `src/exo/shared/types/events.py`, `src/exo/shared/types/tasks.py`, `src/exo/shared/types/worker/__init__.py`, `src/exo/shared/types/worker/runner_response.py` ve 15 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/4216ca541aa32ff33c45d6103f120bb2a3713ae9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4216ca541aa32ff33c45d6103f120bb2a3713ae9) · [Dal](https://github.com/exo-explore/exo/tree/runner-refactor-2).


### 250. runner-shutdown-vs-failed

Geçici runner hatasıyla kurtarılamayan hatayı ayırır. Planlayıcı ve supervisor yalnızca geri dönülemeyen hata durumlarında runner'ı kapatacak şekilde düzenlenir.

**Windows katkısı:** Windows–Mac runner kararlılığı açısından ilgili; işletim sistemi desteği eklemekten bağımsızdır.

**Durum:** 1 ileri / 121 geri; 5 değişen dosya; son commit `c6fab7fa`, 2026-03-25T16:46:06Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix: only shutdown runners that error unrecoverably. Dosyalar: `src/exo/shared/types/worker/runners.py`, `src/exo/worker/plan.py`, `src/exo/worker/runner/image_models/runner.py`, `src/exo/worker/runner/llm_inference/runner.py`, `src/exo/worker/runner/runner_supervisor.py`. [Sabit commit](https://github.com/exo-explore/exo/commit/c6fab7fa972c6865f2778f9c3cc5c3fd0f1cc68e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...c6fab7fa972c6865f2778f9c3cc5c3fd0f1cc68e) · [Dal](https://github.com/exo-explore/exo/tree/runner-shutdown-vs-failed).


### 251. rust-explore-2

Rust networking ve Python bağlayıcılarının sadeleştirildiği keşif dalıdır. Eski keşif/swarm/yardımcı kodu kaldırıp yönlendirme, seçim ve worker bağlantı akışını değiştirir.

**Windows katkısı:** Heterojen ağ katmanı tasarımına fikir verir; Windows veya RTX 5070 yürütme desteği doğrulaması değildir.

**Durum:** 1 ileri / 269 geri; 39 değişen dosya; son commit `45a9f32f`, 2026-02-17T11:44:23Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: woahg. Dosyalar: `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md`, `README.md`, `app/EXO/EXO/ExoProcessController.swift` ve 34 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/45a9f32fc70661d8b9da17f7d20cac69692f303e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...45a9f32fc70661d8b9da17f7d20cac69692f303e) · [Dal](https://github.com/exo-explore/exo/tree/rust-explore-2).


### 252. sami/dashboard-tests

Dashboard model başlatma ve chat akışları için Playwright E2E/visual testleri ekler. CI, macmon ve macOS networksetup gereksinimlerini test çalıştırmasına uyarlar.

**Windows katkısı:** M1 dashboard regresyonlarını yakalama açısından ilgili; Windows test ortamı ayrıca uyarlanmalıdır.

**Durum:** 16 ileri / 342 geri; 14 değişen dosya; son commit `d611f553`, 2026-02-04T15:13:58+05:00. Açık PR: [#1364](https://github.com/exo-explore/exo/pull/1364) (taslak).

**Kanıt:** Son commit: testing macmon. Dosyalar: `.github/workflows/pipeline.yml`, `.gitignore`, `dashboard/package-lock.json`, `dashboard/package.json`, `dashboard/playwright.config.ts` ve 9 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/d611f55332f0c201623946d3ba994ab9ae2083da) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...d611f55332f0c201623946d3ba994ab9ae2083da) · [Dal](https://github.com/exo-explore/exo/tree/sami/dashboard-tests).


### 253. sami/flash

FLASH için eklenti mimarisi, iş kuyruğu/yerleştirme akışı ve salloc/sbatch/scancel/squeue CLI araçlarını ekler. Runner ve uzaktan komut istemcisiyle genel görev çalıştırma alanını genişletir.

**Windows katkısı:** Küme iş planlama açısından dolaylı ilgili; RTX 5070 native Windows çıkarım portu değildir.

**Durum:** 19 ileri / 410 geri; 39 değişen dosya; son commit `4d74574e`, 2026-01-30T15:32:57+05:00. Açık PR: [#1127](https://github.com/exo-explore/exo/pull/1127).

**Kanıt:** Son commit: formatting. Dosyalar: `pyproject.toml`, `src/exo/cli/__init__.py`, `src/exo/cli/common.py`, `src/exo/cli/salloc.py`, `src/exo/cli/sbatch.py` ve 34 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/4d74574eddd8af366cdb54f43f494f983eca82b1) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4d74574eddd8af366cdb54f43f494f983eca82b1) · [Dal](https://github.com/exo-explore/exo/tree/sami/flash).


### 254. sami/iOS-app

Swift/Xcode tabanlı EXO iOS uygulaması ve lite node yaklaşımını ekler. Chat, keşif ve yerel inference servisleriyle dashboard/placement tarafında iOS cihaz gösterimi içerir.

**Windows katkısı:** Apple ekosistemi açısından ilgili; mevcut M1–Windows hedefinin doğrudan önceliği düşüktür.

**Durum:** 3 ileri / 267 geri; 44 değişen dosya; son commit `5b81d55d`, 2026-02-19T22:07:34+05:00. Açık PR: [#1524](https://github.com/exo-explore/exo/pull/1524) (taslak).

**Kanıt:** Son commit: lite node. Dosyalar: `app/EXO-iOS/EXO-iOS.xcodeproj/project.pbxproj`, `app/EXO-iOS/EXO-iOS.xcodeproj/project.xcworkspace/contents.xcworkspacedata`, `app/EXO-iOS/EXO-iOS.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved`, `app/EXO-iOS/EXO-iOS/Assets.xcassets/AccentColor.colorset/Contents.json`, `app/EXO-iOS/EXO-iOS/Assets.xcassets/AppIcon.appiconset/AppIcon.png` ve 39 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/5b81d55d662796a74758e4d8ca9ce781414d511f) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5b81d55d662796a74758e4d8ca9ce781414d511f) · [Dal](https://github.com/exo-explore/exo/tree/sami/iOS-app).


### 255. sami/image-gen-safety

Dağıtık görüntü üretimi için model adapter'ları, pipeline ve dashboard görüntü akışını geliştiren geniş tarihsel daldır. FLUX/Qwen görüntü modelleri, yükleme öncesi block budama ve runner olay düzenlemeleri içerir.

**Windows katkısı:** M1 görüntü motorunu korumada fikir verir; dal adındaki safety tek başına doğrulanmış güvenlik veya Windows CUDA desteği değildir.

**Durum:** 189 ileri / 499 geri; 40 değişen dosya; son commit `fc8aaeaf`, 2026-01-07T04:19:43+05:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: small UI change. Dosyalar: `dashboard/src/lib/components/ChatForm.svelte`, `dashboard/src/lib/components/ChatMessages.svelte`, `dashboard/src/lib/stores/app.svelte.ts`, `dashboard/src/routes/+page.svelte`, `pyproject.toml` ve 35 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/fc8aaeaf4893ff0a406be15dc54fb97f3bd159f3) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...fc8aaeaf4893ff0a406be15dc54fb97f3bd159f3) · [Dal](https://github.com/exo-explore/exo/tree/sami/image-gen-safety).


### 256. shard-refactor

Shard/instance tiplerini ve placement yardımcılarını sadeleştirir. Zenoh metrikleri, model kartı storage'u ve instance bağlantılarını taşıyan değişikliklerin üstüne küçük refaktör ekler.

**Windows katkısı:** Windows–Mac yerleştirme yapısına mimari olarak ilgili; ağ değişiklikleri GPU backend desteğini kanıtlamaz.

**Durum:** 3 ileri / 3 geri; 54 değişen dosya; son commit `a79f8ec7`, 2026-06-03T17:11:54+01:00. Açık PR: [#2146](https://github.com/exo-explore/exo/pull/2146).

**Kanıt:** Son commit: small refactor. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 49 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/a79f8ec7b18e93f0a936acb713b8e77d78c363ae) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...a79f8ec7b18e93f0a936acb713b8e77d78c363ae) · [Dal](https://github.com/exo-explore/exo/tree/shard-refactor).


### 257. simplify-downloads

Bu dalın ucu main tarihinin içindedir; main'e göre bağımsız yeni commit bulunmaz. Uç commit'in somut işi dashboard'da PDF sayfalarının metnini ve görüntüsünü gönderen destek eklemektir.

**Windows katkısı:** Windows–M1 arayüzüne tarihsel katkı zaten main'dedir; adı üzerinden yeni indirme çözümü seçilmemelidir.

**Durum:** 0 ileri / 103 geri; 0 değişen dosya; son commit `4688adb5`, 2026-03-31T18:25:40+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Support PDFs in dashboard (#1822). Dosyalar: Bağımsız dosya değişikliği yok. [Sabit commit](https://github.com/exo-explore/exo/commit/4688adb5d276819d65dd64c7b9f7fa7cf5ad5e2e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4688adb5d276819d65dd64c7b9f7fa7cf5ad5e2e) · [Dal](https://github.com/exo-explore/exo/tree/simplify-downloads).


### 258. splitting-rust-rewrite-3

Rust ağ yeniden yazımını Python routing/topic/election akışından ayırıp eski bağlantı ve libp2p bağlayıcılarını temizler. Kimlik kalıcılığı ve ağ örnekleri de düzenlenen kapsamdadır.

**Windows katkısı:** Windows–Mac keşif/yönlendirme mimarisine ilgili; yerel Windows çıkarım motoru eklemez.

**Durum:** 2 ileri / 258 geri; 28 değişen dosya; son commit `5ddc2574`, 2026-02-18T11:40:16Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: smore. Dosyalar: `Cargo.lock`, `Cargo.toml`, `rust/exo_pyo3_bindings/Cargo.toml`, `rust/exo_pyo3_bindings/exo_pyo3_bindings.pyi`, `rust/exo_pyo3_bindings/src/allow_threading.rs` ve 23 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/5ddc2574ec242f3f1a335fd5d5e287be54d96ae8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...5ddc2574ec242f3f1a335fd5d5e287be54d96ae8) · [Dal](https://github.com/exo-explore/exo/tree/splitting-rust-rewrite-3).


### 259. state-manager-2

Olay yönlendirme içinde merkezi state_manager eklemeyi dener. MLX/MFlux engine arayüzü çalışmasını taşıyıp worker response ve layer-loading callback bağımlılıklarını azaltır.

**Windows katkısı:** Karma kümede durumu yönetme tasarımı için ilgili; native Windows GPU uyumluluğu ayrı konudur.

**Durum:** 5 ileri / 55 geri; 33 değişen dosya; son commit `7d949a08`, 2026-04-22T14:15:23+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: workin on it. Dosyalar: `src/exo/api/main.py`, `src/exo/main.py`, `src/exo/master/main.py`, `src/exo/routing/event_router.py`, `src/exo/routing/state_manager.py` ve 28 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7d949a08cf9e4fe63ff451c6d51b14a272d959eb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7d949a08cf9e4fe63ff451c6d51b14a272d959eb) · [Dal](https://github.com/exo-explore/exo/tree/state-manager-2).


### 260. support-mlx-device-backends

API'den runner başlangıcına CPU/GPU/Auto MLX cihaz seçimini taşır. Bootstrap'ta mx.set_default_device çağırarak CPU zorlaması ve varsayılan otomatik seçim sağlar.

**Windows katkısı:** M1 davranışını koruma ve Linux CPU katılımı için ilgili; GPU seçeneği Windows CUDA desteği anlamına gelmez.

**Durum:** 1 ileri / 260 geri; 6 değişen dosya; son commit `f8748ead`, 2026-02-17T10:52:11-08:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Add MLX compute device backend selection (cpu/gpu/auto). Dosyalar: `src/exo/master/api.py`, `src/exo/master/placement.py`, `src/exo/shared/types/api.py`, `src/exo/shared/types/commands.py`, `src/exo/shared/types/worker/instances.py` ve 1 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/f8748eade1a0af635785c1d5c3201d43a56e8667) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...f8748eade1a0af635785c1d5c3201d43a56e8667) · [Dal](https://github.com/exo-explore/exo/tree/support-mlx-device-backends).


### 261. test-app

macOS uygulamasındaki InstanceViewModel.swift üzerinde dar bir düzeltme içerir. Çıkarım motoru veya ağ katmanına yeni bir platform eklemez.

**Windows katkısı:** M1 uygulama görünümüne sınırlı ilgili; Windows RTX 5070 hedefi için önceliği düşüktür.

**Durum:** 1 ileri / 346 geri; 1 değişen dosya; son commit `e4256fa2`, 2026-02-02T17:57:02Z. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: fix InstanceViewModel.swift. Dosyalar: `app/EXO/EXO/ViewModels/InstanceViewModel.swift`. [Sabit commit](https://github.com/exo-explore/exo/commit/e4256fa28498c65e1a63b83c26e8f1c5d7e1bcd8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e4256fa28498c65e1a63b83c26e8f1c5d7e1bcd8) · [Dal](https://github.com/exo-explore/exo/tree/test-app).


### 262. testing

Prefill/decode düzeninin MLX ve vLLM taraflarında biriken optimizasyon deneylerini toplar. vLLM adapter/connector, NVML, NVFP4 model kartları, link-local ağ betikleri ve benchmark değişiklikleri içerir.

**Windows katkısı:** NVIDIA–M1 görev ayrımı için yüksek ilgi taşır; deney dalı native Windows çalışırlığının kanıtı değildir.

**Durum:** 16 ileri / 37 geri; 64 değişen dosya; son commit `84db5691`, 2026-04-29T13:29:36+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: Optimizations 6. Dosyalar: `.envrc`, `.mlx_typings/mlx_lm/models/cache.pyi`, `.mlx_typings/pynvml/__init__.pyi`, `bench/harness.py`, `bench/prefill-decode.toml` ve 59 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/84db56916748cf3582a499cd57d76b2a181338c6) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...84db56916748cf3582a499cd57d76b2a181338c6) · [Dal](https://github.com/exo-explore/exo/tree/testing).


### 263. update-readme-for-spark

README ve PLATFORMS belgelerini DGX Spark desteğini anlatmak üzere günceller. Çalışma motoru değiştirmek yerine platform anlatımı ve sahiplik dosyasını düzenler.

**Windows katkısı:** Linux Spark bilgisini sağlar; dokümantasyon native Windows RTX 5070 desteği olarak genellenemez.

**Durum:** 1 ileri / 55 geri; 3 değişen dosya; son commit `1b22ebd5`, 2026-04-23T12:43:18+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: update readme for dgx spark support. Dosyalar: `.github/CODEOWNERS`, `PLATFORMS.md`, `README.md`. [Sabit commit](https://github.com/exo-explore/exo/commit/1b22ebd51de7952c3d312caf3067201f2b19dadb) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1b22ebd51de7952c3d312caf3067201f2b19dadb) · [Dal](https://github.com/exo-explore/exo/tree/update-readme-for-spark).


### 264. zenoh

Rust taşıma katmanını libp2p'den Zenoh'a geçiren ilk deneylerden biridir. Peer/multicast keşfi, namespace ve bellek storage yapılandırmasıyla Python ağ bağlayıcılarını değiştirir.

**Windows katkısı:** Windows–Mac mesajlaşma için önemli mimari kaynak; yerel Windows derleme/keşif doğrulaması ayrıca gerekir.

**Durum:** 2 ileri / 28 geri; 29 değişen dosya; son commit `e113d42b`, 2026-05-07T13:28:51+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: uncap. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `rust/exo_pyo3_bindings/Cargo.toml` ve 24 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e113d42ba173bf418d6c188cea980922b7e06413) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e113d42ba173bf418d6c188cea980922b7e06413) · [Dal](https://github.com/exo-explore/exo/tree/zenoh).


### 265. zenoh2

Zenoh göçünü sürdürüp Rust bağlayıcılarını exo_rs adı altında toplar. Eski libp2p kodunu ve bootstrap peer kullanımını temizleyen yeniden düzenleme/yeniden tabanlama adımları içerir.

**Windows katkısı:** Karma kümenin bağlantı yapısını etkiler; CUDA veya native Windows desteği eklediği çıkarılamaz.

**Durum:** 16 ileri / 6 geri; 58 değişen dosya; son commit `902c6207`, 2026-05-29T21:40:14+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: deprecate bootstrap peers. Dosyalar: `.envrc`, `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md` ve 53 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/902c6207f3333aab6bd1949b4842b48e70c9c85b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...902c6207f3333aab6bd1949b4842b48e70c9c85b) · [Dal](https://github.com/exo-explore/exo/tree/zenoh2).


### 266. zenoh-chunks

Zenoh üzerinde API yanıt chunk'larını task request/response akışına taşımayı dener. Metrik Last Value, custom model cards ve instance links çalışmalarını da taşıyıp görev atamasını düzenler.

**Windows katkısı:** Windows–M1 görev/stream yönlendirmesi için ilgili; GPU motoru eklemez ve Windows yürütmesi doğrulanmamıştır.

**Durum:** 10 ileri / 5 geri; 103 değişen dosya; son commit `b38bed6e`, 2026-06-03T03:23:35+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: better task assignment. Dosyalar: `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md`, `app/EXO/EXO/ExoProcessController.swift` ve 98 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/b38bed6e17fb5c3b5676077deb7ebbea052f84c8) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b38bed6e17fb5c3b5676077deb7ebbea052f84c8) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-chunks).


### 267. zenoh-chunks2

Chunk taşımayı Zenoh task request/response düzenine alan daha küçük devam dalıdır. Rust session/storage/task modülleri ve task testleriyle görev atama ve yeniden adlandırma değişikliklerini içerir.

**Windows katkısı:** Karma kümede stream taşıma tasarımı için öncelikli; native Windows desteği olduğu söylenemez.

**Durum:** 8 ileri / 3 geri; 68 değişen dosya; son commit `e0974fcc`, 2026-06-03T17:19:45+01:00. Açık PR: [#2147](https://github.com/exo-explore/exo/pull/2147).

**Kanıt:** Son commit: better task assignment. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 63 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e0974fcc28d07854f2935b32a0b2e1fd07304603) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e0974fcc28d07854f2935b32a0b2e1fd07304603) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-chunks2).


### 268. zenoh-dashboard

Zenoh metrik/task/storage akışlarının üstüne dashboard ve indirme görünümünü uyarlar. İndirme Last Value, mailbox ve placement deneyleriyle istemci store/sayfa akışını birlikte değiştirir.

**Windows katkısı:** Windows–Mac küme görünürlüğüne ilgili; altyapı dalı CUDA çalıştırma desteği değildir.

**Durum:** 15 ileri / 3 geri; 80 değişen dosya; son commit `dba1a33c`, 2026-06-03T17:37:00+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: dashboard update. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 75 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/dba1a33c9f974da1c0f7ef70f8066a827db9e71a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...dba1a33c9f974da1c0f7ef70f8066a827db9e71a) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-dashboard).


### 269. zenoh-downloads

Model indirme durumunu Zenoh Last Value semantiğine taşır. Task/chunk ve custom card/instance link altyapısını taşıyarak indirme state'ini yeni yayın akışına bağlar.

**Windows katkısı:** İki cihazın indirme durumunu eşleştirmeye yarar; Windows GPU backend'ini değiştirmez.

**Durum:** 9 ileri / 3 geri; 72 değişen dosya; son commit `fe809223`, 2026-06-03T17:19:59+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: downloads in LV. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 67 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/fe8092232340b23fa0bdec698333dc4d4f1c9c52) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...fe8092232340b23fa0bdec698333dc4d4f1c9c52) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-downloads).


### 270. zenoh-metrics

Düğüm metriklerini olay günlüğü yerine Zenoh Last Value yaklaşımıyla yayınlamaya taşır. Rust session/liveliness bağlayıcısı ve API/master/worker state uygulaması birlikte değişir.

**Windows katkısı:** Windows–M1 cihaz telemetrisi için mimari öncelik taşır; Windows ölçüm toplama ve derleme desteği ayrıca gerekir.

**Durum:** 1 ileri / 1 geri; 25 değişen dosya; son commit `229880a4`, 2026-08-25T18:26:10+01:00. Açık PR: [#2144](https://github.com/exo-explore/exo/pull/2144).

**Kanıt:** Son commit: move metrics to zenoh Last Value semantics. Dosyalar: `Cargo.lock`, `Cargo.toml`, `rust/exo_rs/Cargo.toml`, `rust/exo_rs/exo_rs.pyi`, `rust/exo_rs/src/last_value.rs` ve 20 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/229880a4dea60d4294bac2dbb549571d8e44345b) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...229880a4dea60d4294bac2dbb549571d8e44345b) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-metrics).


### 271. zenoh-nearly

Zenoh göçü, metrik/storage/task, placement ve dashboard çalışmalarını bir araya getirip tutarlılığı düzenler. Eski mimari belgelerini kaldırması da kapsamı geniş bir geçiş dalı olduğunu gösterir.

**Windows katkısı:** Karma küme protokolü için önemli fakat geniş bir deneydir; native Windows GPU desteği sonucuna varılamaz.

**Durum:** 17 ileri / 4 geri; 117 değişen dosya; son commit `e16cbefa`, 2026-06-03T16:59:27+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: consistency. Dosyalar: `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md`, `TODO.md` ve 112 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/e16cbefa427dfd1b2551a369b284fd073afcea8e) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...e16cbefa427dfd1b2551a369b284fd073afcea8e) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-nearly).


### 272. zenoh-placement

Zenoh task/storage altyapısına placement ve mailbox akışını uyarlayan daldır. İndirme Last Value ve görev atama çalışmalarını da taşıdığı için değişiklik sadece yerleştirmeyle sınırlı değildir.

**Windows katkısı:** Windows–M1 yerleştirme/mesajlaşma için ilgili; GPU backend uyumu ayrıca gerekir.

**Durum:** 15 ileri / 4 geri; 113 değişen dosya; son commit `b0f65007`, 2026-06-03T15:52:07+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: not temp. Dosyalar: `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md`, `TODO.md` ve 108 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/b0f650072c01dc566cfd4e6751e58abfa6389884) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...b0f650072c01dc566cfd4e6751e58abfa6389884) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-placement).


### 273. zenoh-placement2

Zenoh placement denemesinin main'e daha yakın başka bir devamıdır. Mailbox/session/storage/task modülleri, yerleştirme akışı ve görev/indirme durumları birlikte değişir.

**Windows katkısı:** Karma kümenin kontrol akışına ilgili; yerel Windows yürütmesi doğrulanmamıştır.

**Durum:** 14 ileri / 3 geri; 76 değişen dosya; son commit `1601e141`, 2026-06-03T17:20:15+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: not temp. Dosyalar: `Cargo.lock`, `Cargo.toml`, `dashboard/src/lib/components/ChatSidebar.svelte`, `dashboard/src/lib/components/PrefillDecodeDisaggregation.svelte`, `dashboard/src/lib/stores/app.svelte.ts` ve 71 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/1601e14136b40ec590c7cdbcecf6afcfd836f49d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...1601e14136b40ec590c7cdbcecf6afcfd836f49d) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-placement2).


### 274. zenoh-storage

Custom model cards ve prefill/decode instance bağlantılarını Zenoh storage'a taşır. Last Value metrik altyapısı, storage handle bağlayıcısı ve API/state düzenlemeleri içerir.

**Windows katkısı:** Windows–M1 konfigürasyon paylaşımı için ilgili; engine/VRAM uyumluluğunu çözmez.

**Durum:** 2 ileri / 3 geri; 35 değişen dosya; son commit `72897dd9`, 2026-06-03T17:09:18+01:00. Açık PR: [#2145](https://github.com/exo-explore/exo/pull/2145).

**Kanıt:** Son commit: custom model cards + instance links. Dosyalar: `Cargo.lock`, `Cargo.toml`, `rust/exo_rs/Cargo.toml`, `rust/exo_rs/exo_rs.pyi`, `rust/exo_rs/src/last_value.rs` ve 30 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/72897dd9da47a29fefacb7f1e54c5447aca4ff7a) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...72897dd9da47a29fefacb7f1e54c5447aca4ff7a) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-storage).


### 275. zenoh-tasks

Zenoh üzerinde görev iletimi için task/storage ve Python plan/runner akışını yeniden düzenler. Metrikler, custom model cards ve instance links çalışmaları da aynı kısa deney dalında bulunur.

**Windows katkısı:** Karma kümede görev taşıma tasarımına yarar; Windows CUDA motoru sağladığı iddia edilemez.

**Durum:** 5 ileri / 5 geri; 90 değişen dosya; son commit `aa79f7d5`, 2026-06-02T22:34:40+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: small refactor. Dosyalar: `AGENTS.md`, `Cargo.lock`, `Cargo.toml`, `MISSED_THINGS.md`, `app/EXO/EXO/ExoProcessController.swift` ve 85 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/aa79f7d5c2cdf64df955e655d216d7dc734f2fdf) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...aa79f7d5c2cdf64df955e655d216d7dc734f2fdf) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-tasks).


### 276. zenoh-temp

İlk Zenoh göçüne JSON state proxy katmanı ekler. Rust state bağlayıcısı ve Python yönlendirme/state akışı bu geçici temsil etrafında düzenlenir.

**Windows katkısı:** Windows–Mac state paylaşımına fikir verir; Windows çalışma/derleme desteği doğrulanmış değildir.

**Durum:** 3 ileri / 28 geri; 32 değişen dosya; son commit `7ed3eaa6`, 2026-05-07T15:36:03+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: json state proxy. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `rust/exo_pyo3_bindings/Cargo.toml` ve 27 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/7ed3eaa61708b41adc8255b8965deec6771ee29d) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...7ed3eaa61708b41adc8255b8965deec6771ee29d) · [Dal](https://github.com/exo-explore/exo/tree/zenoh-temp).


### 277. zenohize

Zenoh geçişinde API stream aktarımını ve JSON state proxy'yi birleştirir. Rust bağlayıcılarını exo_net adı altında yeniden düzenleyip point-to-point iletişim ekler.

**Windows katkısı:** Windows–Mac API stream mimarisi için ilgili; çıkarım backend desteğinden ayrı değerlendirilmelidir.

**Durum:** 4 ileri / 28 geri; 61 değişen dosya; son commit `ded78404`, 2026-05-08T16:04:25+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: api streams. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `justfile` ve 56 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/ded7840499bfb0605e5539c2b617c5d49acafa31) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...ded7840499bfb0605e5539c2b617c5d49acafa31) · [Dal](https://github.com/exo-explore/exo/tree/zenohize).


### 278. zenohize2

Zenoh API streams denemesinin alternatif devamıdır. libp2p göçü, exo_net bağlayıcı adı ve point-to-point iletişim düzenini taşır; commit dizisi zenohize ile aynı değildir.

**Windows katkısı:** Karma küme stream tasarımına fikir verir; Windows GPU desteği kanıtı yoktur.

**Durum:** 3 ileri / 28 geri; 60 değişen dosya; son commit `4430b0da`, 2026-05-07T17:07:40+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: api streams. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `justfile` ve 55 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/4430b0daf9a3e06cf4aa7553eee766e948d52569) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...4430b0daf9a3e06cf4aa7553eee766e948d52569) · [Dal](https://github.com/exo-explore/exo/tree/zenohize2).


### 279. zenohize3

Zenoh API streams/JSON state geçişine özel keşif düzenlemesinin ikinci denemesini ekler. exo_net, ağ topolojisi ve yönlendirme yollarını birlikte değiştirir.

**Windows katkısı:** Windows–Mac keşif tasarımı açısından ilgili; native Windows bağlantı çalışırlığı ayrıca doğrulanmalıdır.

**Durum:** 5 ileri / 28 geri; 60 değişen dosya; son commit `adefd341`, 2026-05-09T00:48:21+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: custom discovery take 2. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `justfile` ve 55 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/adefd3415bc52e680b20b37b107c0dd7866db284) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...adefd3415bc52e680b20b37b107c0dd7866db284) · [Dal](https://github.com/exo-explore/exo/tree/zenohize3).


### 280. zenohize4

Zenoh API/state ve özel keşif çalışmalarını yeniden tabanlama düzeltmesiyle sürdürür. Rust bağlayıcı yeniden adlandırması, point-to-point iletişim ve ağ yönlendirme göçü kapsamındadır.

**Windows katkısı:** Karma küme ağ katmanı için inceleme kaynağıdır; native Windows CUDA portu olarak seçilemez.

**Durum:** 7 ileri / 25 geri; 63 değişen dosya; son commit `9c251647`, 2026-05-09T09:53:40+01:00. Açık PR: Eşleşen açık upstream PR yok.

**Kanıt:** Son commit: rebase fix. Dosyalar: `Cargo.lock`, `Cargo.toml`, `flake.lock`, `flake.nix`, `justfile` ve 58 diğer dosya. [Sabit commit](https://github.com/exo-explore/exo/commit/9c25164744dc2927c8d0547ac22eda53992cdca9) · [Sabit karşılaştırma](https://github.com/exo-explore/exo/compare/21a54c5ea0230a3bec1e1a786d200126c7e34ec6...9c25164744dc2927c8d0547ac22eda53992cdca9) · [Dal](https://github.com/exo-explore/exo/tree/zenohize4).


## Kaynaklar

[GitHub dallar API sayfa 1](https://api.github.com/repos/exo-explore/exo/branches?per_page=100&page=1),
[sayfa 2](https://api.github.com/repos/exo-explore/exo/branches?per_page=100&page=2),
[sayfa 3](https://api.github.com/repos/exo-explore/exo/branches?per_page=100&page=3).
[Main sabit commit](https://github.com/exo-explore/exo/commit/21a54c5ea0230a3bec1e1a786d200126c7e34ec6).
[Açık PR API](https://api.github.com/repos/exo-explore/exo/pulls?state=open&per_page=100).
Her dalın sabit commit ve karşılaştırma linki kendi bölümündedir.
