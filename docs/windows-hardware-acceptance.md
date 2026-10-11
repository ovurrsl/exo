# Windows ve M1 fiziksel küme kabulü

Bu kontrol listesi RTX 5070 PC ile iki M1 Air A2337 üzerinde çalıştırılır. Her düğüm
aynı fork kaynaklarını kullanmalı; yalnız Mac'in MLX Metal bağımlılığı kendi mevcut
kilidinden kurulmalıdır. Yerel Windows testleri bu fiziksel matrisin yerine geçmez.
CLI ve masaüstü API portu **52415** olarak kalır.

## Hazırlık

1. PC ile her Mac arasında çalışır bir IP bağlantısı kurun. IPv6 discovery ve
   birbirine ulaşabilen adresleri doğrulayın. USB4 P2P/TB Bridge adaptörünün gerçek
   adını tanılamadan alın; örnek IP veya adaptör adını olduğu gibi kullanmayın.
2. Windows'ta yalnız güvenilir bağlantıyı Private olarak işaretleyin. Paketlenmiş
   uygulamanın firewall yardımcısını kullanın; normal uygulama yönetici çalışmaz.
   Mac firewall ayarının aynı düğümlere izin verdiğini doğrulayın.
3. Bütün düğümlerde aynı namespace seçin. Mac uygulamasındaki namespace ayarı
   desteklenir; açık CLI argümanı ortam değişkenini geçersiz kılar.
4. Qwen3-0.6B-4bit modelinin aynı 40 karakterlik Hugging Face revision'ını, tokenizer
   dosyalarını ve download metadata'sını her düğüme koyun. Metadata olmadan CUDA
   snapshot sözleşmesi kontrollü hata verir. Model dosyalarını kopyalarken
   `.cache/huggingface/download` veya `.exo-revisions` dizinini de koruyun.
5. Log ve kabul çıktıları için ayrı bir klasör kullanın; aktif kullanıcı EXO_HOME
   veya modellerinin üzerine yazmayın. Mac'lerin çip/RAM/macOS sürümlerini, PC'nin
   sürücü sürümünü ve bağlantı türünü rapora kaydedin.

## Ring testi

Yetkilendirilmiş SSH anahtarıyla PC'den iki rank sırasını tek komutla çalıştıran
denetleyici kullanılabilir. Komutu repo kökünde çalıştırın; gerçek PC IP'sini ve
Mac hesabını kullanın, her tekrar için yeni bir `--output` dizini verin:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/windows/check_mixed_ring.py `
  --ssh-target melisaovur@192.168.1.105 --pc-ip 192.168.1.101 `
  --ssh-key build/acceptance/mac-test-ssh-key `
  --known-hosts build/acceptance/mac-known-hosts `
  --output build/acceptance/physical-mixed-ring
```

Sistem SSH istemcisi kullanılamıyorsa `--ssh C:\path\ssh.exe` ekleyin. Komut parola
istemeden mevcut yetkili anahtarı ve doğrulanmış host kaydını kullanır; anahtar
oluşturmaz veya Mac erişim ayarını değiştirmez. Mac'te yalnız ayrı
`exo-windows-acceptance/21a54c5e-shared` checkout'u ve onun `build` dizini kullanılır.
Komut, 21a54c5e tabanını, sabit Mac MLX kaynak commit'ini, gerçek Metal kernel'ini ve kritik
protokol kaynaklarının frozen Windows manifest'indeki hash'lerini doğrular.
Her rank için sekiz dtype/boyut collective kaydı ve normal worker çıkış kodu 7
gerekir. Windows runtime'ın dosya bütünlüğü ilk rank çalıştırılmadan denetlenir.
Süre aşımında yerel sahip olunan süreçler ve Mac'teki ayrı test process group'u
kapatılır; özgün EXO.app ve kullanıcı süreçleri hedeflenmez. Kaynak/MLX kimliği
her Mac rank başlamadan tekrar okunur. Kaynaktan derleme tarihi sürüm etiketini
değiştirebilir; tam commit ve Git repo kimliği kurulu paketin `direct_url.json`
kaydından doğrulanır. Windows manifest, engine ve MLX kimliği raporda tutulur.

`mixed-ring.json` içindeki `physical_ring_verified` yalnız iki sıra da geçerse
true olur. `model_inference_verified` false kalır; bu kapı pipeline/model kabulü
yerine geçmez. SSH, Metal veya ring hazır değilse başarısızlık raporu yazılır ve
komut çıkış 1 verir. İkinci Mac ve üç düğüm matrisi ayrıca çalıştırılmalıdır.

Önce PC ve bir Mac için `hosts.json` hazırlayın. Adresleri gerçek ulaşılabilir
adreslerle değiştirin. Test portları ring için ayrıdır; ürünün 52415 portunu
değiştirmez. Kullanılan portların boş olduğunu doğrulayın.

```json
[
  ["MAC1_IP:59001"],
  ["PC_IP:59002"]
]
```

Her iki düğümde aynı dosya ve rank sırası kullanılmalıdır. İki komutu birbirine
yakın zamanda çalıştırın. Mac üzerinde aynı fork'taki kontrol scripti kullanılır;
Mac'in MLX wheel'i değiştirilmez.

```bash
# Mac, rank 0; exo checkout kökünden
MLX_HOSTFILE="$PWD/hosts.json" MLX_RANK=0 \
  uv run --no-sync python scripts/windows/mlx/check_mlx.py \
  --worker ring --device gpu --exo-hook
```

```powershell
# Windows, rank 1; exo checkout kökünden
$env:MLX_HOSTFILE = (Resolve-Path .\hosts.json).Path
$env:MLX_RANK = '1'
.\dist\windows\exo\exo.exe --runtime-check --worker ring --device gpu --exo-hook
if ($LASTEXITCODE -ne 7) { throw 'Fiziksel ring testi başarısız' }
Remove-Item Env:MLX_RANK, Env:MLX_HOSTFILE
```

Başarılı worker çıkış kodu 7'dir; hata veya zaman aşımı başarılı kabul edilmez.
Script FP32/FP16/BF16/int32, sum/max/min/gather, send/recv ve büyük strided
verileri sınar. Mac rank 0 ve PC rank 1 sırasını değiştirerek tekrarlayın.
Sonra üç adresli hostfile ile Mac1/Mac2/PC için rank 0/1/2 kullanın ve sırayı
değiştirin. M1'lerde JACCL/RDMA testi bu matrisin parçası değildir.

## Model ve toparlanma

Ürün portu üzerinden test için ayrı namespace ve veri klasörleriyle düğümleri
başlatın. Mac örneği:

```bash
EXO_HOME="$PWD/build/physical-acceptance/mac1" \
  uv run --no-sync exo --namespace exo-windows-physical-acceptance --offline --no-downloads
```

Windows kaynak örneği:

```powershell
$env:EXO_HOME = Join-Path $PWD 'build\physical-acceptance\pc'
.\dist\windows\exo\exo.exe --namespace exo-windows-physical-acceptance --offline --no-downloads
```

Her düğüm aynı API portunu kullanmalıdır; peer erişim kontrolü yerel API portunu
kullanır. Placement öncesinde iki yönlü topoloji bağlantılarını ve Metal/CUDA
backend bildirimlerini doğrulayın.

Model dizinleri varsayılan EXO_HOME dışında kalıyorsa read-only model kökünü ayrıca
ayarlayın: Windows'ta `EXO_MODELS_READ_ONLY_DIRS` noktalı virgülle, Mac'te iki
noktayla ayrılır. Her makinede o makineye ait gerçek yolu kullanın. Kök, normalize
model klasörünü içeren üst dizindir; tek modelin alt klasörünü kök olarak vermeyin.

Dashboard'dan pipeline instance oluşturun; layer dağılımı, snapshot, tokenizer ve
precision'ı kaydedin. CUDA içeren çok düğümlü tensor modu varsayılan kapalıdır.
İlk kabulte bunu açmayın.

| Matris | Tekrarlar |
| --- | --- |
| RTX 5070 tek başına | Sohbet, vision, cache ve normal kapanış |
| İki M1 | Mevcut Mac-only baseline ile fork karşılaştırması |
| PC ve Mac1 | Master/rank sırası iki yönde |
| PC ve Mac2 | Master/rank sırası iki yönde |
| PC ve iki Mac | Master her düğümde, rank sıraları değiştirilerek |

Her satırda sabit prompt ile üretim, tekrarlanan sohbet, uzun context, prefix
cache açık/kapalı ve stream iptali sonrası tekrar üretim çalıştırın. Sayısal
karşılaştırmada precision'a uygun tolerans kullanın; Metal ile CUDA'nın bit
düzeyinde aynı floating point sonucu verdiğini varsaymayın.

Bir peer'ı uyutma/bağlantısını kesme ve tekrar bağlama durumlarını test edin.
Sadece ilgili test düğümlerini yönetin. Bekleme zaman aşımı, bütün CUDA instance'ının
kaldırılması ve yeni instance'ta üretimin toparlanmasını kaydedin. Farklı yerel cache
eşikleri kullanıldığında collective sırasının bozulmadığını ayrıca sınayın.

## Temiz Windows kurulumu

Ayrı Python/uv/Node/Rust kurulumu gerektirmeyen kabul kiti hazırlanabilir:

```powershell
./scripts/windows/build-acceptance-kit.ps1 -OutputDirectory build/consumer-kit
```

Oluşan `exo-windows-acceptance-kit.zip` dosyasını temiz Windows sisteminde açın.
`consumer-acceptance.md` içindeki komut kurulu `exo.exe` ve paketli kütüphanelerle
GPU/JIT/spawn, yerel ring, gerçek 2 GiB üzeri shard, sohbet, uzun context,
stream iptali ve normal worker kapanışını sınar. Model ağırlıkları ayrı ve
revision metadata'sıyla birlikte sağlanmalıdır. Loglar yeni çıktı dizininde
korunur. Kit varsayılan olarak geliştirici araçları algılanırsa kabulü reddeder;
`-AllowDeveloperMachine` yalnız yerel smoke testi içindir ve temiz Windows
başarısı ilan etmez. `-PreflightOnly` hardware testi değildir. Runtime kabulü,
kurulum/kaldırma ve native UI/güncelleme kabulünün yerine geçmez.

Tek RTX 5070 üzerinde Schnell üretim ve giriş görüntüsüyle düzenleme kabulü:

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/windows/check_image_inference.py `
  --model-dir C:\verified-models --runtime dist/windows/exo/exo.exe `
  --output build/acceptance/frozen-image-edit --exercise-edit
```

Bu kapı 512x512 / dört adım / sabit seed ile üretimi, partial çıktı sonrası iptali,
toparlanmayı ve normal worker kapanışını doğrular. Düzenlemede aynı prompt/seed
ile iki farklı renkli girişin farklı final PNG üretmesi gerekir; iptalden sonraki
aynı giriş aynı sonucu üretmelidir. Kabul kapsamı tek CUDA düğümünde Schnell
img2img'dir; maskeli düzenleme, diğer model aileleri ve karma image pipeline
ayrı donanım testleri gerektirir.

Windows test komutlarında `-X utf8` konsol çıktılarını da UTF-8 yapar. Özellikle
Çince/emoji içeren çıktı dizinlerinde yerel konsol kod sayfasının sonuç mesajını
yazmasını engellemesini önler. Windows CI işleri `PYTHONUTF8=1` kullanır.

Bu aşama geliştirici bilgisayarından ayrı bir sistem/VM gerektirir. Python, uv,
Rust, Node, Visual Studio ve CUDA Toolkit bulunmamalıdır. Uyumlu NVIDIA sürücüsü
olan fiziksel GPU kullanılmalıdır; GPU geçişi olmayan VM inference kabulü sayılmaz.

Çevrimdışı WebView2 kurulumunu, boşluk/Türkçe karakter içeren yolları, başlangıçta
durdurmayı, çift açılışı, yabancı port çakışmasını ve GUI çökmesinde worker ağacının
kapanmasını doğrulayın. Ayar sonrası restart, DPI/klavye erişimi, modelleri koruyan
kaldırma ve imzalı paket güncellemesini sınayın. İmza anahtarı olmayan yerel review
paketi signed-updater kabulü yerine geçmez.

Her sonucu cihaz/OS/sürücü, fork source hash'i, wheel hash'i, model revision'ı,
komutlar, rank sırası, loglar, süreler ve exit code ile kaydedin. Atlanan veya
donanımı olmayan kapıyı başarılı işaretlemeyin.

## Mevcut Mac ve sürüm tabanı — 9 Ekim 2026

192.168.1.105:52415 API'si salt okunur sorguda Apple M1, MacBook Air,
8 GiB RAM, macOS 27.0.1 (26A434) bildirdi. O anda kullanılabilir RAM
2.959.851.520 bayttı; bu ölçüm anlık olduğundan yerleştirmede tekrar okunmalıdır.
Mevcut uygulama v1.0.71 (fd707de30b42db4211d15da96b9052e1dc280ed1), libp2p
routing ve eski state şemasını kullanıyor. Kullanıcının belirlediği karma test
Mac tabanı 21a54c5ea0230a3bec1e1a786d200126c7e34ec6'dır; Windows fork'u da
bu upstream tabanıyla karşılaştırıldı. Eski uygulama korunacak, ayrı kaynak
checkout/test ortamı kullanılacak. Snapshot/cache capability collective'leri
her iki rank'ta aynı sıra ile çalışmalıdır; yalnız commit numarası benzerliği
kararlı karma inference kanıtı sayılmaz. Swift/Metal/JACCL kaynakları korunur.

SSH doğrulandı; ayrı Mac test checkout'u
`/Users/melisaovur/exo-windows-acceptance/21a54c5e-shared` hazırdır. Ortak çekirdek
testleri 102 geçti, 1 atlandı. PC→Mac ve Mac→PC TCP echo testleri 59001/59002
geçici portlarında başarılıdır; firewall ayarı değiştirilmedi. Bunlar Metal–CUDA
ring collective kabulü değildir. Pinned Qwen3-0.6B modeli ayrı test model dizinine
revision metadata'sıyla kopyalandı; mevcut kullanıcı modelleri değiştirilmedi.

Mac Metal derleyicisi henüz bulunmadığından sabit MLX kaynak derlemesi bekliyor.
Xcode kurulup ilk açılışı tamamlandıktan sonra global `xcode-select` değiştirmeden
yalnız test komutunun ortamında aşağıdaki seçimi kullanın:

```bash
cd "$HOME/exo-windows-acceptance/21a54c5e-shared"
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
xcrun --find metal
PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH" \
  UV_CACHE_DIR="$HOME/exo-windows-acceptance/uv-cache" \
  CMAKE_BUILD_PARALLEL_LEVEL=2 CARGO_BUILD_JOBS=2 \
  uv sync --frozen --extra mlx
```

`xcrun` hâlâ hata verirse GPU kabulünü başarılı saymayın; Xcode Metal bileşeni ve
ilk açılış gereksinimi çözülmelidir. Mac bağımlılık pin'ini değiştirmek bu kapının
yerine geçmez. `--extra mlx` gereklidir; yalnız `uv sync --frozen` mevcut kaynak
tabanında Metal runtime'ı kurmaz.

## İki cihazlı güncel kabul — 10 Ekim 2026

Sabit Mac MLX kaynak commit'i `cc3f3e60` Xcode ile, yalnız izole derleme için
resmî Metal 17F109 compiler seçicisi kullanılarak derlendi. Global Xcode seçimi,
Swift kaynakları ve Darwin dependency pin'leri korunmuştur. İlk paragraftaki
Metal derleyicisi bekleme durumu önceki tarihe aittir.

Windows engine `e3e29f50ca6aee003bd65a1f7ec9f56d3abff287324a0f801d154f9f320d004f`
ile RTX 5070 + tek M1 üzerinde Mac-master, Windows-master ve Windows doğrudan
stop kabulü geçti. Her denemede Qwen3-0.6B aynı snapshot ile iki rank'a bölündü,
üç sohbet tamamlandı ve iki worker ile iki node exit 0 verdi. On kritik ortak
kaynak hash'i eşleşti; geçici namespace/test portları kullanıldı. Ürün varsayılanı
52415'tir. Kanıtların hash özeti
`build/acceptance/health-handle-final-physical-matrix-20261010.json` içindedir.

İkinci M1, üç cihaz, uzun üretim sırasında fiziksel bağlantı kopması ve karma
image/tensor/disaggregated kabulü bu sonuçların kapsamına girmez. Ayrıca geliştirici
PC'sindeki kurulum temiz Windows kabulü değildir. İzole Mac test süreçleri ve
kimliği doğrulanmış geçici caffeinate guard temizlendi; mevcut EXO değiştirilmedi.
