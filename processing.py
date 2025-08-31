# processing.py (colon-separated drawtext options; fixed)
import os, json, subprocess, tempfile, shutil

def _run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout)
    return p.stdout

def _which(name):
    return shutil.which(name) is not None

def ensure_ffmpeg():
    if not (_which("ffmpeg") and _which("ffprobe")):
        raise RuntimeError("ffmpeg/ffprobe non trovati nel PATH.")

def ffprobe_streams(path):
    out = _run(["ffprobe","-v","error","-show_streams","-of","json", path])
    data = json.loads(out)
    return data.get("streams", [])

def select_primary_audio_index(streams):
    audio_streams = [s for s in streams if s.get("codec_type")=="audio"]
    if not audio_streams:
        return None
    def score(s):
        lang = (s.get("tags",{}) or {}).get("language","").lower()
        ch = s.get("channels",0) or 0
        is_default = 1 if (s.get("disposition",{}).get("default",0)==1) else 0
        sc = 0
        if lang=="ita": sc += 100
        elif lang in ("eng","en"): sc += 90
        sc += ch * 5
        sc += is_default * 2
        return sc
    best = max(audio_streams, key=score)
    return best.get("index")

def get_video_params(path):
    streams = ffprobe_streams(path)
    v = next((s for s in streams if s.get("codec_type")=="video"), None)
    if not v:
        raise RuntimeError("Nessuna traccia video trovata in %s" % path)
    w = int(v.get("width",1920))
    h = int(v.get("height",1080))
    r = v.get("r_frame_rate","25/1")
    try:
        num, den = r.split("/")
        fps = float(num)/float(den) if float(den)!=0 else 25.0
    except Exception:
        fps = 25.0
    return w,h,fps

DEFAULT_FONT_PATH = os.environ.get("DEFAULT_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")

def build_lowerthird_drawtext(text, fontfile=None, fontsize=56, margin_x=60, margin_y=80, box_opacity=0.55, duration=10.0):
    text_escaped = text.replace("\\", r"\\\\").replace(":", r"\:").replace("'", r"\'").replace(",", r"\,")
    parts = [
        f"drawtext=text='{text_escaped}'",
        f"x={margin_x}",
        f"y=h-th-{margin_y}",
        "fontcolor=white",
        f"fontsize={fontsize}",
        "box=1",
        f"boxcolor=black@{box_opacity}",
        "boxborderw=24",
        "alpha=1",
        f"enable='lte(t,{float(duration)})'"
    ]
    if fontfile:
        parts.append(f"fontfile='{fontfile}'")
    return ":".join(parts)

def process_segment(inp, outp, target_w, target_h, target_fps, audio_index=None,
                    lower_text=None, lower_duration=0, fontfile=None, fontsize=56,
                    denoise=False, hp_hz=80, lp_hz=16000, compressor=True,
                    lufs_target=-16.0, tp_limit=-0.1):
    vf_parts = [
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease",
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2"
    ]
    if lower_text and lower_duration>0:
        vf_parts.append(build_lowerthird_drawtext(lower_text, fontfile=fontfile, fontsize=fontsize, duration=lower_duration))
    vf_parts.append("format=yuv420p")
    vf = ",".join(vf_parts)

    af_parts = [f"highpass=f={hp_hz}", f"lowpass=f={lp_hz}"]
    if denoise:
        af_parts.append("afftdn=nr=20")
    if compressor:
        af_parts.append("acompressor=threshold=-18dB:ratio=3:attack=5:release=80:makeup=6")
    af_parts.append(f"loudnorm=I={lufs_target}:TP={tp_limit}:LRA=11")
    af = ",".join(af_parts)

    map_args = []
    if audio_index is not None:
        map_args = ["-map","0:v:0","-map",f"0:{audio_index}"]
    else:
        map_args = ["-map","0:v:0","-map","0:a:0?"]

    cmd = [
        "ffmpeg","-y","-i", inp,
        "-r", f"{target_fps}",
        "-filter:v", vf,
        *map_args,
        "-c:v","libx264","-preset","medium","-crf","18",
        "-c:a","aac","-b:a","192k","-ar","48000",
        "-filter:a", af,
        outp
    ]
    _run(cmd)

def process_interview(intro, main, outro, lower, lower_duration, fontfile, fontsize,
                      denoise, lufs_target, tp_limit, out_path):
    ensure_ffmpeg()
    w,h,fps = get_video_params(main)
    with tempfile.TemporaryDirectory() as td:
        tmp_intro = os.path.join(td, "00_intro.mp4")
        tmp_main  = os.path.join(td, "01_main.mp4")
        tmp_outro = os.path.join(td, "02_outro.mp4")

        process_segment(intro, tmp_intro, w,h,fps,
                        audio_index=select_primary_audio_index(ffprobe_streams(intro)),
                        lower_text=None, lower_duration=0, fontfile=fontfile, fontsize=fontsize,
                        denoise=False, lufs_target=lufs_target, tp_limit=tp_limit)

        process_segment(main, tmp_main, w,h,fps,
                        audio_index=select_primary_audio_index(ffprobe_streams(main)),
                        lower_text=lower, lower_duration=lower_duration, fontfile=fontfile, fontsize=fontsize,
                        denoise=denoise, lufs_target=lufs_target, tp_limit=tp_limit)

        process_segment(outro, tmp_outro, w,h,fps,
                        audio_index=select_primary_audio_index(ffprobe_streams(outro)),
                        lower_text=None, lower_duration=0, fontfile=fontfile, fontsize=fontsize,
                        denoise=False, lufs_target=lufs_target, tp_limit=tp_limit)

        list_path = os.path.join(td, "files.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for p in (tmp_intro, tmp_main, tmp_outro):
                f.write(f"file '{p}'\n")

        try:
            _run(["ffmpeg","-y","-f","concat","-safe","0","-i", list_path, "-c","copy", out_path])
        except RuntimeError:
            _run(["ffmpeg","-y","-f","concat","-safe","0","-i", list_path,
                  "-c:v","libx264","-preset","medium","-crf","18",
                  "-c:a","aac","-b:a","192k","-ar","48000",
                  "-movflags","+faststart", out_path])
