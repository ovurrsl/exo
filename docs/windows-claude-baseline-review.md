# Önceki Claude Windows çalışmalarının incelemesi

10 Ekim 2026 tarihinde değişmez `21a54c5e..931e0ff4` aralığı incelendi:
26 Claude ortak imzalı commit, 37 dosya. Değişen Python/Rust kaynakları,
testler, bağımlılıklar, PowerShell build dosyaları ve MLX patch'i okundu.
Bu, tam repo güvenlik taraması değildir.

## Korunan temel

| Commit | Çalışma | Mevcut durum |
|---|---|---|
| `dd922460` | Windows spawned runner stdio ve pipe okuma | Windows yolu korunur; Unix yolu ayrıdır |
| `a9dd8577` | Windows pidfile paylaşım kilidi ve discovery watcher | PID kontrolü yerine OS kilidi korunur |
| `3de4c76a` | Windows veri dizinleri ve sistem bilgisi | Windows'a özel dizinler korunur |
| `1d22673c`, `22b11afe` | Yerelleştirilmiş Wi-Fi Direct ve USB4 P2P tanıma | Ağ bağdaştırıcısı tanıma korunur |
| `0ff0dd1a`, `931e0ff4` | Winsock ring portu ve byte-exact MLX patch | Sabit kaynak ve LF patch korunur |

Eski değişikliklerde Mac MLX kaynak commit'i yükseltilmemiştir. Yeni çalışma
da Swift dosyalarını, Metal/JACCL yolunu ve Darwin dependency pin'lerini korur.

## Sonraki düzeltmelerin gerekçesi

| Eski davranış | Sorun | Mevcut düzeltme |
|---|---|---|
| NVML hatasında sistem RAM'ine geçiş | VRAM'e sığmayan model yerleştirilebilir | Windows kapasitesi güvenli şekilde sıfırlanır; override VRAM ile sınırlandırılır |
| `f8501f04`: MLX cache değerinin VRAM'e eklenmesi | CUDA sayacı pinned host buffer'larını da içerebilir | Cache temizlenir, gerçek NVML boş belleği yeniden okunur |
| Her rank'ın yerel cache döngüsü | Farklı eşik/sıra collective'leri kilitleyebilir | Ortak karar, sabit boyutlu sıra metadata'sı ve boş rank katılımı |
| Yayınlanan eski wheel | Build makinesinin DLL yolları ve 2 GiB dosya sınırı | Taşınabilir `+win.3` wheel, Unicode yollar ve zorunlu büyük dosya kontrolü |
| Windows sinyallerine dayanan kapanış | Worker ağacı düzgün boşaltılamayabilir | Named Event, supervisor sahipliği ve normal runner çıkışının beklenmesi |

`5555ca6c` raporundaki karma MLX ring testi Linux CPU süreçleri arasında yapılmıştı.
Winsock veya fiziksel Mac/Windows kabulü olarak gösterilmemelidir. Sonraki yerel
raporlar RTX 5070 + tek M1 üzerinde her iki rank/master sırasını ve gerçek
3.093.767.283 baytlık safetensors dosyasını kapsar; inceleme sırasında bu
donanım testleri yeniden çalıştırılmadı.

## Açık takip maddeleri

- **P2 — ring connect retry socket sızıntısı:** MLX v0.32.3'ten gelen
  `TCPSocket::connect`, başarısız denemelerde eski socket'i kapatmadan yeni
  socket oluşturur. Mevcut patch bunu değiştirmez. Kaynak:
  `mlx/distributed/utils.cpp`, `TCPSocket::connect`. Yeni bir wheel düzeltmesi
  yapılırsa kaynak/patch/wheel hash'leri ve ring hata kabulü tekrar doğrulanmalıdır.
- Mevcut `+win.3` provenance yalnız `120a-real;120-virtual` içerir. RTX 20–40
  için destek iddiası yapılmaz; eski çok mimarili wheel ile karıştırılmamalıdır.
- Aynı bağımlılıklarla eski `931e0ff4` dashboard ve mevcut dashboard tip
  kontrolü, aynı 9 dosyada **15 hata / 6 uyarı** verir. Mevcut Windows image
  fit testleri 9/9 ve production build geçer; dashboard tip kontrolü geçti
  şeklinde raporlanmaz.
- İkinci M1/üç cihaz, temiz Windows, imzalı güncelleme ve çalışan kaynak
  güvenlik taraması ayrı yayın kapılarıdır.
