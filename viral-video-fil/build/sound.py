import json, numpy as np, subprocess, wave
from scipy.signal import butter, sosfilt, fftconvolve
SR = 44100
TL = json.load(open('timeline.json')); TOTAL = TL[-1]['start'] + TL[-1]['dur']; N = int((TOTAL + 1) * SR)
S = {o['id']: o for o in TL}; st = lambda k: S[k]['start']; en = lambda k: S[k]['start'] + S[k]['dur']
rs = np.random.default_rng(11); t = np.arange(N) / SR
def filt(x, f, typ, o=2): return sosfilt(butter(o, f, typ, fs=SR, output='sos'), x)
lp = lambda x, f: filt(x, f, 'low'); hp = lambda x, f: filt(x, f, 'high'); bp = lambda x, a, b: filt(x, [a, b], 'band')
def place(buf, sig, at, g=1.0):
    i = int(at * SR); j = min(len(buf), i + len(sig))
    if j > i >= 0: buf[i:j] += g * sig[:j - i]
def env(n, a, r):
    e = np.ones(n); A, R = int(a * SR), int(r * SR)
    if A: e[:A] = np.linspace(0, 1, A)
    if R: e[-R:] *= np.linspace(1, 0, R) ** 2
    return e
def reverb(x, sec=2.5, mix=.3, seed=1):
    n = int(sec * SR); ir = np.random.default_rng(seed).standard_normal(n) * np.exp(-np.linspace(0, 7, n)); ir = lp(ir, 5000)
    wet = fftconvolve(x, ir)[:len(x)]; wet *= (np.max(np.abs(x)) + 1e-9) / (np.max(np.abs(wet)) + 1e-9); return x * (1 - mix) + wet * mix
def ramp(a, b, fa=.8, fb=.8):  # 0..1 gate between times a,b with fades
    return np.clip((t - a) / fa, 0, 1) * np.clip((b - t) / fb, 0, 1)

D = 73.42  # D2
# ---- drone (D + A, slow beating) and pad
drone = sum(np.sin(2 * np.pi * f * t + k) * g for k, (f, g) in enumerate([(D, .5), (D * 1.003, .35), (D * 1.5, .3), (D * 2, .25), (D * 3, .08), (D * 4.01, .05)]))
drone = lp(drone, 900) * (.75 + .25 * np.sin(2 * np.pi * t / 9))
# ---- ney-like melody in D Hijaz (D Eb F# G A Bb C)
HIJ = [0, 1, 4, 5, 7, 8, 10, 12, 13, 16]
def ney(phrase, at, buf, base=D * 4):
    tt0 = at
    for deg, dur in phrase:
        L = int(dur * SR); tt = np.arange(L) / SR; f = base * 2 ** (HIJ[deg] / 12) * (1 + .006 * np.sin(2 * np.pi * 5.2 * tt) * np.clip(tt / .3, 0, 1))
        ph = 2 * np.pi * np.cumsum(f) / SR; tone = np.sin(ph) + .25 * np.sin(2 * ph) + .08 * np.sin(3 * ph)
        breath = bp(rs.standard_normal(L), f.mean() * .8, f.mean() * 2.5) * .25
        place(buf, (tone + breath) * env(L, .12, min(.35, dur * .5)), tt0); tt0 += dur * .92
melody = np.zeros(N)
P1 = [(4, .8), (5, .5), (4, .5), (2, .9), (1, .6), (0, 1.6)]
P2 = [(0, .5), (1, .5), (2, .9), (4, .6), (5, .5), (6, .5), (5, .5), (4, 1.4)]
P3 = [(7, .7), (6, .5), (5, .5), (4, .8), (2, .5), (1, .6), (0, 2.0)]
ney(P1, st('intro') + 1.2, melody); ney(P2, st('yemen') + .6, melody); ney(P3, st('yemen') + 4.8, melody)
ney(P2, st('quote') + 1.0, melody); ney(P1, st('sura') + .8, melody); ney(P3, st('sura') + 4.3, melody); ney(P1, st('outro') + .2, melody, D * 2)
melody = reverb(melody, 3.0, .45, 2)
# ---- frame drum
def doum():
    L = int(.6 * SR); tt = np.arange(L) / SR; f = 62 + 40 * np.exp(-tt * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 6) + lp(rs.standard_normal(L), 400) * np.exp(-tt * 40) * .5
def tek():
    L = int(.15 * SR); tt = np.arange(L) / SR; return bp(rs.standard_normal(L), 1500, 6000) * np.exp(-tt * 45) * .8 + np.sin(2 * np.pi * 420 * tt) * np.exp(-tt * 50) * .3
DO, TE = doum(), tek(); drums = np.zeros(N); beat = 60 / 92
def pattern(a, b, dense=False):
    k = 0; x = a
    while x < b:
        s = k % 8
        if s in (0, 3): place(drums, DO, x, 1.0)
        if s in (2, 5, 6) or (dense and s in (1, 4, 7)): place(drums, TE, x, .55 if s != 6 else .4)
        if dense and s == 7: place(drums, DO, x, .6)
        x += beat / 2; k += 1
pattern(st('march') + .1, en('camels') - .3); pattern(st('birds') + 1.0, en('birds') - .2, True)
place(drums, DO, st('kneel') + .1, .8)
drums = reverb(drums, 1.6, .22, 3)
music = drone * .55 * (1 - .5 * ramp(st('birds'), en('birds'))) + melody * .5 + drums * .9
music *= np.clip(t / 2, 0, 1) * np.clip((TOTAL + .4 - t) / 3, 0, 1)

# ---- SFX
sfx = np.zeros(N)
def whoosh(d=.6):
    L = int(d * SR); n = rs.standard_normal(L); o = np.zeros(L)
    for k in range(24): a, b = k * L // 24, (k + 1) * L // 24; c = 300 * (16) ** (k / 24); o[a:b] = bp(n, c * .7, min(c * 1.4, 18000))[a:b]
    return o * np.sin(np.pi * np.linspace(0, 1, L)) ** 2
def boom(g=1.0):
    L = int(2.5 * SR); tt = np.arange(L) / SR; f = 30 + 60 * np.exp(-tt * 8)
    return reverb(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 2) + lp(rs.standard_normal(L), 2500) * np.exp(-tt * 12) * .4, 2.5, .3, 4) * g
def trumpet(d=1.4, pitch=1.0):
    L = int(d * SR); tt = np.arange(L) / SR; x = tt / d
    f = pitch * (330 + 260 * np.sin(np.pi * np.clip(x * 1.4, 0, 1)) - 60 * x) * (1 + .02 * np.sin(2 * np.pi * 7 * tt))
    ph = 2 * np.pi * np.cumsum(f) / SR; saw = sum(np.sin(ph * h) / h for h in range(1, 14))
    v = bp(saw, 700, 2600) * 1.4 + bp(saw, 2800, 4200) * .6 + bp(rs.standard_normal(L), 1000, 4000) * .3
    return reverb(np.tanh(v * 2.5) * env(L, .06, .4), 2.0, .3, 6)
def march_rumble(a, b):
    L = int((b - a) * SR); tt = np.arange(L) / SR; base = lp(rs.standard_normal(L), 180) * 2
    steps = np.zeros(L)
    for k in range(int((b - a) / .23)): place(steps, lp(rs.standard_normal(int(.08 * SR)), 900) * np.exp(-np.arange(int(.08 * SR)) / SR * 40), k * .23 + rs.uniform(0, .05), rs.uniform(.3, .7))
    clank = np.zeros(L)
    for k in range(int((b - a) * 3)): f = rs.uniform(2500, 5000); n = int(.06 * SR); place(clank, np.sin(2 * np.pi * f * np.arange(n) / SR) * np.exp(-np.arange(n) / SR * 70), rs.uniform(0, b - a), rs.uniform(.05, .15))
    return (base * .5 + steps + clank) * env(L, .8, .8)
def flutter(d):
    L = int(d * SR); o = np.zeros(L)
    for k in range(int(d * 140)): n = int(.05 * SR); place(o, hp(rs.standard_normal(n), 600) * np.hanning(n), rs.uniform(0, d), rs.uniform(.05, .3))
    return lp(o, 5000)
def whistle():
    L = int(.7 * SR); tt = np.arange(L) / SR; f = 2600 * np.exp(-tt * 1.6) + 500
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(L, .05, .1) * .25 + bp(rs.standard_normal(L), 1500, 5000) * env(L, .2, .1) * .15
def thud():
    L = int(.4 * SR); tt = np.arange(L) / SR; return np.sin(2 * np.pi * 55 * tt) * np.exp(-tt * 14) + lp(rs.standard_normal(L), 1500) * np.exp(-tt * 25) * .5
WH = whoosh()
for o in TL[1:]: place(sfx, WH, o['start'] - .45, .5)
place(sfx, boom(), st('intro') + .3, .8)
place(sfx, trumpet(1.5), st('march') + .9, .55)
place(sfx, march_rumble(st('march'), en('march') + .3), st('march'), .35)
place(sfx, march_rumble(st('kneel'), en('kneel')), st('kneel'), .2)
k = S['kneel']; kt = k['voStart'] + k['voDur'] * .55
place(sfx, trumpet(1.1, .8), kt - .3, .4); place(sfx, boom(), kt + .9, .6)
b = S['birds']; place(sfx, flutter(b['dur'] + .3), b['start'], .22)
R = np.random.default_rng(5)
for _ in range(70): x = b['start'] + R.uniform(2.3, 6.3); place(sfx, whistle(), x - .7, R.uniform(.15, .35)); place(sfx, thud(), x, R.uniform(.15, .35))
place(sfx, boom(), st('sura') + .1, .5)
wind = hp(lp(rs.standard_normal(N), 700), 90) * (.4 + .6 * np.sin(2 * np.pi * t / 6.7) ** 2) * .35
sfx += wind * np.clip((TOTAL + .4 - t) / 3, 0, 1)

# ---- VO + ducking + mix
vo = np.zeros(N); duck = np.ones(N)
for o in TL:
    w = wave.open(f"vo/{o['id']}.wav"); x = np.frombuffer(w.readframes(w.getnframes()), np.int16) / 32768.0
    place(vo, x, o['voStart']); duck[int(o['voStart'] * SR):int((o['voStart'] + o['voDur']) * SR)] = .4
duck = np.convolve(duck, np.ones(int(.15 * SR)) / int(.15 * SR), 'same')
vo = hp(vo, 90); vo = vo + .12 * reverb(vo, .6, 1.0, 5); vo /= np.max(np.abs(vo)) + 1e-9
music /= np.max(np.abs(music)) + 1e-9; sfx /= np.max(np.abs(sfx)) + 1e-9
mix = vo + music * duck * .42 + sfx * duck * .5
mix = (np.tanh(mix * 1.1) * .9)[:int(TOTAL * SR)]
bed = (music * duck * .42 + sfx * duck * .5)[:len(mix)]; dl = int(.012 * SR)
stt = np.stack([mix, mix], 1); stt[dl:, 1] += bed[:-dl] * .15; stt[dl:, 0] -= bed[:-dl] * .05
w = wave.open('mix_raw.wav', 'wb'); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(stt, -1, 1) * 32767).astype(np.int16).tobytes()); w.close()
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', 'mix_raw.wav', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=9', '-ar', '48000', 'mix.wav'], check=True)
print('ok', round(TOTAL, 2))
