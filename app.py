# app.py
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from werkzeug.utils import secure_filename
from processing import process_interview, DEFAULT_FONT_PATH

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "./uploads")
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "./outputs")
MAX_CONTENT_LENGTH_MB = float(os.environ.get("MAX_CONTENT_LENGTH_MB", "4096"))  # 4 GB default

app = Flask(__name__)
@app.route("/health")
def health():
    return "ok", 200
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
app.config["MAX_CONTENT_LENGTH"] = int(MAX_CONTENT_LENGTH_MB * 1024 * 1024)

ALLOWED_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".MP4", ".MKV", ".MOV"}

def ensure_dirs():
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["OUTPUT_FOLDER"], exist_ok=True)

@app.route("/", methods=["GET"])
def index():
    ensure_dirs()
    return render_template("index.html", default_font=DEFAULT_FONT_PATH)

@app.route("/process", methods=["POST"])
def process():
    ensure_dirs()

    # Validate inputs
    intro_file = request.files.get("intro")
    main_file  = request.files.get("main")
    outro_file = request.files.get("outro")
    lower_text = (request.form.get("lower") or "").strip()
    lower_duration = float(request.form.get("lower_duration") or "10")
    fontsize = int(request.form.get("fontsize") or "56")
    denoise = bool(request.form.get("denoise"))
    lufs = float(request.form.get("lufs") or "-16")
    tp = float(request.form.get("tp") or "-0.1")
    fontfile = (request.form.get("fontfile") or "").strip()
    out_name = (request.form.get("out") or "intervista_finale.mp4").strip()
    if not out_name.lower().endswith(".mp4"):
        out_name += ".mp4"

    if not intro_file or not main_file or not outro_file or not lower_text:
        flash("Carica intro, main, outro e inserisci il testo del sottopancia.", "error")
        return redirect(url_for("index"))

    def _save(file_storage):
        fname = secure_filename(file_storage.filename)
        ext = os.path.splitext(fname)[1]
        if ext not in ALLOWED_VIDEO_EXTS:
            raise ValueError(f"Estensione non supportata: {ext}")
        uid = str(uuid.uuid4())[:8]
        path = os.path.join(app.config["UPLOAD_FOLDER"], f"{uid}_{fname}")
        file_storage.save(path)
        return path

    try:
        intro_path = _save(intro_file)
        main_path  = _save(main_file)
        outro_path = _save(outro_file)
    except Exception as e:
        flash(f"Errore upload: {e}", "error")
        return redirect(url_for("index"))

    job_id = str(uuid.uuid4())[:12]
    output_path = os.path.join(app.config["OUTPUT_FOLDER"], f"{job_id}_{secure_filename(out_name)}")

    try:
        process_interview(
            intro=intro_path,
            main=main_path,
            outro=outro_path,
            lower=lower_text,
            lower_duration=lower_duration,
            fontfile=fontfile or DEFAULT_FONT_PATH,
            fontsize=fontsize,
            denoise=denoise,
            lufs_target=lufs,
            tp_limit=tp,
            out_path=output_path
        )
    except Exception as e:
        flash(f"Errore di elaborazione: {e}", "error")
        return redirect(url_for("index"))

    return redirect(url_for("result", job_id=job_id))

@app.route("/result/<job_id>")
def result(job_id):
    # Find the file with prefix job_id_
    for name in os.listdir(app.config["OUTPUT_FOLDER"]):
        if name.startswith(f"{job_id}_"):
            file_name = name
            break
    else:
        return "Output non trovato.", 404
    return render_template("result.html", job_id=job_id, file_name=file_name)

@app.route("/download/<job_id>")
def download(job_id):
    for name in os.listdir(app.config["OUTPUT_FOLDER"]):
        if name.startswith(f"{job_id}_"):
            path = os.path.join(app.config["OUTPUT_FOLDER"], name)
            return send_file(path, as_attachment=True, download_name=name)
    return "File non trovato.", 404

if __name__ == "__main__":
    ensure_dirs()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)
