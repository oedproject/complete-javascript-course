# Generates Turkish narration with Google TTS (gTTS) and builds build/timeline.json
import json, subprocess, os
from gtts import gTTS
os.chdir(os.path.dirname(os.path.abspath(__file__)))
S = json.load(open('script.json')); os.makedirs('build/vo', exist_ok=True)
t = 0; tl = []
for s in S:
    raw, out = f"build/vo/{s['id']}_raw.mp3", f"build/vo/{s['id']}.wav"
    gTTS(s['say'], lang='tr').save(raw)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-af',
        'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,atempo=1.28',
        '-ar', '44100', '-ac', '1', out], check=True)
    d = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out]))
    lead = .9 if s['rank'] == 1 else (.5 if s['id'] == 'intro' else .2); tail = {'outro': 1.5}.get(s['id'], .2)
    tl.append(dict(s, start=round(t, 3), dur=round(lead + d + tail, 3), voStart=round(t + lead, 3), voDur=round(d, 3))); t += lead + d + tail
json.dump(tl, open('build/timeline.json', 'w'), ensure_ascii=False, indent=1)
print('total', round(t, 2))
