# Altı upstream PR incelemesi — 10 Ekim 2026

Altı PR'ın fork dalları güncellendi; upstream PR'lar **açık ve birleştirilmemiş**
durumda. Aşağıdaki sabit head'ler GitHub metadata'sı ve temiz yerel worktree
HEAD'leriyle doğrulandı. **Bu PR dalları `windows-native` ana dalına topluca
birleştirilmedi.** Özellikle PR 2305 DNS pinleme ve PR 2306 model yolu
düzeltmeleri, güncel `79de2150` masaüstü kaynağı veya `7d11c690` frozen runtime
içindedir denemez; seçili entegrasyon ve regresyon doğrulaması açıktır.

| PR                                                                              | İncelenen immutable head                   | Sonuç                                                                                                                              |
| ------------------------------------------------------------------------------- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| [2308 — NIC hız bilgisi](https://github.com/exo-explore/exo/pull/2308)          | `d0a422d9baf2b305c08d5cca088c6731f004b2f3` | Ürün kodu korundu; eski strict şemanın yeni alanları reddettiği uyumluluk sınırı açıklamaya eklendi.                               |
| [2307 — Qwen3 model kartı](https://github.com/exo-explore/exo/pull/2307)        | `3d84adc1007518485648fc73c25a0dfc7cd3aa31` | Tensor boyutu 2.262.920.192 bayt olarak düzeltildi; mimari ve sampling bilgileri doğrulandı.                                       |
| [2306 — ModelId/yol güvenliği](https://github.com/exo-explore/exo/pull/2306)    | `a0b7e2276ca8973878c35e5d538bcf246f08f5f0` | Windows drive/ADS ve ayrılmış adlar; model/cache kökü, symlink/junction kaçışı ve kökün kendisini silme kontrolleri güçlendirildi. |
| [2305 — image URL SSRF](https://github.com/exo-explore/exo/pull/2305)           | `20946ec72ab4b6031947b0a5bfaf1f6fcab5527a` | Async DNS, zaman sınırı, doğrulanmış IP'ye pinleme, redirect engeli ve ortam proxy'sini kullanmama tamamlandı.                     |
| [2304 — workspace test belgeleri](https://github.com/exo-explore/exo/pull/2304) | `ffcb9850b7d994ec932da7f745641e94b08b2679` | Belge değişikliği korundu; `exo_tools` import'u ile `tools` workspace üyeliği doğrulandı.                                          |
| [2303 — namespace belgesi](https://github.com/exo-explore/exo/pull/2303)        | `efbc9554ace53ba44ce3d832f696ae523732c5e5` | Kaynaktan çalışan CLI için gerçek `--namespace` davranışı belgelendi; yalnız environment değişkeni yeterli değildir.               |

## Doğrulama ve sınırlar

**2308.** Önceki geniş CPU incelemesinde 111 test geçti, üç mevcut test atlandı.
Yerel `worktrees/pr-2308-nic-core-pytest.log` sayıyı korur; tam selector komutu
bu eski logda bulunmaz. Taze sabit-head çalışmasında
`test_system_info.py` **7 geçti**, `test_tb_parsing.py` **iki macOS testi
atlandı**; bu dar çalışma 111-test kapsamının tekrarı değildir. Yeni alanların
opsiyonel default'ları eski payload'ları kabul eder; eski `extra=forbid`
şeması yeni alanları null olsa bile reddeder. Karışık sürümler aynı cluster'da
uyumlu kabul edilmez; aynı build ve değerlendirme sırasında ayrı discovery
namespace gerekir. `ifconfig -m` sözdizimi ve medya adları Apple kaynaklarıyla
incelendi; gerçek Mac capture'ı ve link throughput ölçümü yapılmadı.

**2307.** Kart 36 katman, hidden size 2560, 8 KV head, 40960 context ve mevcut
MLX Metal/CUDA/CPU backend'lerini tanımlar. Boyut değeri modelin
[sabit safetensors index metadata'sının](https://huggingface.co/mlx-community/Qwen3-4B-4bit/commit/4dcb3d101c2a062e5c1d4bb173588c54ea6c4d25)
tensor-byte toplamıdır; EXO'nun RAM yerleştirme sözleşmesiyle
eşleşir. Önceki incelemede gerçek `ModelCard` loader'ı, mimari/backend/sampling
assertion'ları ve **56 placement/sampling testi** geçti. Taze çalışmada açık
selector'ları kaydedilen **58 test** geçti: 23 placement, 23 placement_utils,
iki custom-model-card apply ve 10 reasoning-parameter. Sayılar farklı
selector'lara aittir. Ayrı senkron TOML/strict ModelCard/sampling assertion'ları
da geçti. Taze async loader denemesi, dosya okunmadan önce Windows Proactor
socketpair başlangıcında 20 saniye sınırına takıldı; fresh async-loader
başarısı doğrulanmadı. Senkron fallback aynı production parser/validator'ı
kullanır, async dosya yolunun kabulü değildir. Model ağırlığı indirme veya
fiziksel üretim yapılmadı.

**2306.** `ModelId`, boş/dot segmentleri, backslash, colon/drive/ADS, Windows
ayrılmış adları ve ortak `caches` adını reddeder. Silme, model ve cache
hedeflerinin tümünü herhangi bir silmeden önce çözümler; kökün kendisini ve
kök dışına çıkan hedefleri reddeder. Taze `test_model_id.py` +
`test_model_dirs.py` çalışmasında **51 geçti**. Önceki daha geniş inceleme
**153 geçti, bir atlandı** sonucu verdi; bu geniş sonuç tarihsel tool
çıktısıdır, taze 51-test logunun kapsamına eklenmez.

**2305.** URL doğrulaması tek başına DNS rebinding'i kapatmıyordu; artık
socket'in kullandığı resolver doğrulanmış IP'lerle sınırlı. Async çözümlemenin
10 saniye sınırı, kısa HTTP timeout'u, `allow_redirects=False` ve
`use_env_proxy=False` devrede. Taze `test_image_url_validation.py`
çalışmasında **29 geçti, bir atlandı**; atlanan API-import testi Windows'ta
POSIX `resource` modülü nedeniyle çalışmıyor. Önceki geniş incelemede
**189 geçti, iki atlandı**; bu sayı tarihsel tool çıktısıdır. DNS değişimi ve
ortam proxy'si testleri ile gerçek aiohttp request/response yolu üzerinden
redirect kontrolü vardır; bütün native upstream suite'inin geçtiği iddiası yoktur.

**2304.** `tests/conftest.py` gerçekten `exo_tools` import ediyor;
`pyproject.toml` gerçekten `tools` workspace üyesini tanımlıyor. Belge,
platforma uygun MLX extra'sıyla `uv sync --all-packages` adımını ekliyor.
Mevcut Windows ortamı temiz clone/kurulum deneyi olarak sunulmadı; kaynak ve
belge tutarlılığı doğrulandı.

**2303.** Eski `EXO_LIBP2P_NAMESPACE` startup'ta reddediliyor.
`EXO_ZENOH_NAMESPACE` CLI'de loglanıyor; namespace argümanının default'u
EXO version. İncelemede gerçek `Args` sınıfı AST üzerinden çalıştırıldı:
yalnız environment ile `0.3.70`, belgelenen
`--namespace my-dev-cluster` ile `my-dev-cluster`. Mac app environment
eşlemesi ayrıca incelendi. Bu belge düzeltmesidir; runtime davranışı değişmez.
Tam Unix application Windows'ta çalıştırılmadı.

İlgili incelemelerde Ruff/format kontrolleri geçti. Bütün native Nix/MLX
suite'i bu Windows host'ta kabul edilmiş değildir: POSIX/MLX collection
sınırları ve PR 2307/2308 full basedpyright sonuçlarında kurulu `pynvml`
paketi için bir mevcut unnecessary-ignore diagnostic'i korundu. Bu kısıtlar
başarılı odak testlerine ek başarı olarak yazılmadı.

## Hosted CI durumu

10 Ekim 2026 metadata kontrolünde altı head'in legacy status
listesi boştu. PR-triggered `ci-pipeline` run'ları **`action_required`**
sonucuyla tamamlanmış ve job listeleri boştu:

| PR   | Workflow                                                                   |
| ---- | -------------------------------------------------------------------------- |
| 2303 | [38066282053](https://github.com/exo-explore/exo/actions/runs/38066282053) |
| 2304 | [34579087493](https://github.com/exo-explore/exo/actions/runs/34579087493) |
| 2305 | [38066502551](https://github.com/exo-explore/exo/actions/runs/38066502551) |
| 2306 | [38066508464](https://github.com/exo-explore/exo/actions/runs/38066508464) |
| 2307 | [38066275592](https://github.com/exo-explore/exo/actions/runs/38066275592) |
| 2308 | [37229461704](https://github.com/exo-explore/exo/actions/runs/37229461704) |

Bu sonuç **test başarısızlığı veya yeşil CI değildir**; upstream workflow
işlemi/onayı ve native CI sonucu beklenir. Review sırasında dış mesaj,
yorum veya workflow rerun gönderilmedi.

## Kanıt kaydı

Taze test logları yerel ana checkout `exo/build/acceptance/` altındadır:

- `pr-2305-focused-verified-20261010.log`: tam `20946ec7` kaynağında 29 geçti/1 skip.
- `pr-2306-focused-verified-20261010.log`: tam `a0b7e227` kaynağında 51 geçti.
- `pr-2307-verified-20261010.log`: head/worktree/import bağlama ve açık selector'lar; 58 geçti, senkron kart assertion'ları geçti; async loader sınırı korundu.
- `pr-2308-verified-20261010.log`: head/worktree/import bağlama; system-info 7 geçti, iki macOS skip.
- `pr-models-nic-verification-20261010.md`: bu iki taze çalışmanın komutları, sabit HF metadata kaynağı ve async loader sınırı.

PR 2307/2308 açıklama düzeltmelerinin önceki metinleri yerel
`reports/pr-review-2307-update.json` ve `reports/pr-review-2308-update.json`
kayıtlarında, güncel açıklamaları bağlantılı PR'lardadır. Eski geniş test
sayıları review tool çıktılarından aktarılır; olmayan log yolu yaratılmadı
ve bu belge yeni güvenlik taraması değildir.
[Windows güncel ilerlemesi](windows-progress-20261010.md) ve
[masaüstü kabulü](windows-desktop-acceptance-20261010.md) entegrasyon sınırını
ayrıca kaydeder.
