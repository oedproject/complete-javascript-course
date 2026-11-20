import json, numpy as np, subprocess, wave
from scipy.signal import butter, sosfilt, fftconvolve
SR = 44100
TL = json.load(open('timeline.json')); TOTAL = TL[-1]['start'] + TL[-1]['dur']
N = int((TOTAL + 1.0) * SR)
rs = np.random.default_rng(7)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def hp(x, f, o=2): return sosfilt(butter(o, f, 'high', fs=SR, output='sos'), x)
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def place(buf, sig, t, g=1.0):
    i = int(t * SR); j = min(len(buf), i + len(sig))
    if i < 0: sig = sig[-i:]; i = 0
    if j > i: buf[i:j] += g * sig[:j - i]
def env(n, a, r):
    e = np.ones(n); A = int(a * SR); R = int(r * SR)
    if A: e[:A] = np.linspace(0, 1, A)
    if R: e[-R:] *= np.linspace(1, 0, R) ** 2
    return e
def reverb(x, sec=2.5, mix=.25, seed=1):
    n = int(sec * SR); ir = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.linspace(0, 7, n))
    ir = lp(ir, 6000); wet = fftconvolve(x, ir)[:len(x)]; wet /= (np.max(np.abs(wet)) + 1e-9) / (np.max(np.abs(x)) + 1e-9)
    return x * (1 - mix) + wet * mix

starts = {o['id']: o['start'] for o in TL}
t_first = starts['munzur']; t_agri = starts['agri']; t_out = starts['outro']
BPM = 96; beat = 60 / BPM; bar = beat * 4
# ---------------- MUSIC ----------------
music = np.zeros(N); t = np.arange(N) / SR
# chord progression (Am F C G) roots in Hz; voices root,5th,octave,10th
prog = [(110.0, [0, 7, 12, 15, 19]), (87.31, [0, 7, 12, 16, 19]), (130.81, [0, 7, 12, 16, 19]), (98.0, [0, 7, 12, 16, 19])]
pad = np.zeros(N); bass = np.zeros(N)
nb = int(TOTAL / bar) + 2
for b in range(nb):
    root, iv = prog[b % 4]; s = b * bar; L = int(bar * SR) + int(.6 * SR)
    tt = np.arange(L) / SR; seg = np.zeros(L)
    for k in iv:
        f = root * 2 ** (k / 12)
        for det in (-.12, 0, .12):  # detuned saws (band-limited-ish via few harmonics)
            ff = f * 2 ** (det / 12)
            for h in range(1, 7): seg += np.sin(2 * np.pi * ff * h * tt + h) / h * .05
    seg *= env(L, .5, .6); place(pad, seg, s)
    bl = int(bar * SR); bt = np.arange(bl) / SR
    bs = (np.sin(2 * np.pi * root / 2 * bt) + .3 * np.sin(2 * np.pi * root * bt)) * env(bl, .02, .2)
    place(bass, bs, s)
pad = lp(pad, 1800)
# filter opens over time -> crude: blend darker/brighter
pad_dark = lp(pad, 600); prog_open = np.clip((t - 2) / (t_agri - 2), 0, 1)
pad = pad_dark * (1 - prog_open) + pad * prog_open
pad = reverb(pad, 3.0, .35, 2)
music += pad * .9 + lp(bass, 220) * .55 * (t > t_first - .02)
# drums
def kick():
    L = int(.45 * SR); tt = np.arange(L) / SR; f = 45 + 110 * np.exp(-tt * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 7) + .3 * rs.standard_normal(L) * np.exp(-tt * 120)
def hat():
    L = int(.08 * SR); return hp(rs.standard_normal(L), 7000) * np.exp(-np.arange(L) / SR * 60)
def snare():
    L = int(.3 * SR); tt = np.arange(L) / SR
    return bp(rs.standard_normal(L), 1200, 6000) * np.exp(-tt * 18) * .7 + np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 25) * .5
drums = np.zeros(N); K, Hh, S = kick(), hat(), snare()
bt_ = t_first
while bt_ < t_out + bar * 1.5:
    i = round((bt_ - t_first) / beat)
    quiet = (t_agri - 3.2) < bt_ < t_agri + .05   # break before #1
    if not quiet:
        place(drums, K, bt_, .9 if i % 2 == 0 else .55)
        if i % 4 in (1, 3): place(drums, S, bt_, .45)
        place(drums, Hh, bt_ + beat / 2, .35)
        if bt_ > t_agri: place(drums, Hh, bt_ + beat / 4, .2); place(drums, Hh, bt_ + 3 * beat / 4, .2)
    bt_ += beat
drums = reverb(drums, 1.2, .15, 3)
fade_out = np.clip((TOTAL + .3 - t) / 2.5, 0, 1)
music = (music + drums * .8) * fade_out * np.clip(t / 1.5, 0, 1)

# ---------------- SFX ----------------
sfx = np.zeros(N)
def whoosh(d=.55, lo=300, hi=5000):
    L = int(d * SR); tt = np.linspace(0, 1, L); n = rs.standard_normal(L)
    out = np.zeros(L); steps = 24
    for k in range(steps):
        a, b = k * L // steps, (k + 1) * L // steps; c = lo * (hi / lo) ** (k / steps)
        out[a:b] = bp(n, c * .7, min(c * 1.4, 18000))[a:b]
    return out * np.sin(np.pi * tt) ** 2
def impact():
    L = int(2.2 * SR); tt = np.arange(L) / SR; f = 32 + 70 * np.exp(-tt * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2.2)
    crack = lp(rs.standard_normal(L), 3500) * np.exp(-tt * 14) * .6
    return reverb(sub + crack, 2.5, .3, 4)
def tick(f=2400):
    L = int(.025 * SR); tt = np.arange(L) / SR; return np.sin(2 * np.pi * f * tt) * np.exp(-tt * 260)
def riser(d):
    L = int(d * SR); tt = np.arange(L) / SR; x = tt / d; n = rs.standard_normal(L)
    out = np.zeros(L); steps = 40
    for k in range(steps):
        a, b = k * L // steps, (k + 1) * L // steps; c = 400 * (12000 / 400) ** (k / steps)
        out[a:b] = bp(n, c * .7, min(c * 1.4, 19000))[a:b]
    tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (x * 3)) / SR) * .25
    return (out * .8 + tone) * x ** 2.2
IMP = impact(); WH = whoosh()
for o in TL:
    s = o['start']
    if o['id'] != 'intro': place(sfx, WH, s - .4, .55)
    if o['rank']:
        g = 1.0 if o['rank'] > 1 else 1.6
        place(sfx, IMP, s + .1, g * .9)
        # counter ticks: easeIO from lt .6 to 2.2 -> faster in middle
        last = -1
        for k in range(160):
            u = k / 160; e = 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2
            v = int(e * 24)
            if v != last: place(sfx, tick(2000 + v * 40), s + .6 + u * 1.6, .18); last = v
        place(sfx, tick(3200) * 2, s + 2.2, .3)
place(sfx, riser(3.0), t_agri - 3.0, .6)
place(sfx, IMP, starts['intro'] + .55, .7)            # title hit
place(sfx, IMP, t_out + .1, .6)
# wind bed
wind = lp(rs.standard_normal(N), 500) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 7.3) ** 2)
wind = hp(wind, 80) * .35
sfx += wind * fade_out

# ---------------- VO + ducking ----------------
vo = np.zeros(N); duck = np.ones(N)
for o in TL:
    w = wave.open(f"vo/{o['id']}.wav"); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.0
    place(vo, x, o['voStart'], 1.0)
    i, j = int(o['voStart'] * SR), int((o['voStart'] + o['voDur']) * SR); duck[i:j] = .38
duck = np.convolve(duck, np.ones(int(.15 * SR)) / int(.15 * SR), 'same')
vo = hp(vo, 90); vo = vo + .12 * reverb(vo, .6, 1.0, 5)  # small room
vo *= 1.0 / (np.max(np.abs(vo)) + 1e-9)
music *= 1 / (np.max(np.abs(music)) + 1e-9)
sfx *= 1 / (np.max(np.abs(sfx)) + 1e-9)
mix = vo * 1.0 + music * duck * .38 + sfx * .45
mix = np.tanh(mix * 1.1) * .9
mix = mix[:int(TOTAL * SR)]
st = np.stack([mix, mix], 1)
# subtle stereo width for music/sfx via delay on right
d = int(.012 * SR); bed = (music * duck * .38 + sfx * .45)[:len(mix)]
st[d:, 1] += bed[:-d] * .15; st[:, 0] -= np.r_[np.zeros(d), bed[:-d]] * .05
pcm = (np.clip(st, -1, 1) * 32767).astype(np.int16)
w = wave.open('mix_raw.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes()); w.close()
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', 'mix_raw.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=9', '-ar', '48000', 'mix.wav'], check=True)
# separate stems for the user
for name, sig in (('stem_music', music * duck), ('stem_sfx', sfx), ('stem_vo', vo)):
    p = (np.clip(sig[:len(mix)] * .8, -1, 1) * 32767).astype(np.int16); w = wave.open(name + '.wav', 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(p.tobytes()); w.close()
print('ok', TOTAL)
