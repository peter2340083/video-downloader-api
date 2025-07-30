from flask import Flask, request, send_file, Response, stream_with_context, after_this_request
from flask_cors import CORS
import yt_dlp
import subprocess
import os
import threading
import time

app = Flask(__name__)
CORS(app)

@app.route('/progress')
def progress():
    url = request.args.get('url')
    dl_type = request.args.get('type', 'video')  # video 或 audio
    if not url:
        return "Missing URL", 400

    if dl_type == 'audio':
        format_opt = 'bestaudio'
        ydl_command = ['yt-dlp', url, '-f', format_opt, '--extract-audio', '--audio-format', 'mp3']
    else:
        format_opt = 'best[ext=mp4]/best'
        ydl_command = ['yt-dlp', url, '-f', format_opt]

    def generate():
        process = subprocess.Popen(
            ydl_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        for line in iter(process.stdout.readline, ''):
            line = line.rstrip('\n')
            yield f"data: {line}\n\n"
        process.stdout.close()
        process.wait()

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def delayed_delete_file(path, delay=3600):
    # 延遲刪除函式，等待 delay 秒後嘗試刪除
    time.sleep(delay)
    try:
        os.remove(path)
        print(f"已刪除檔案: {path}")
    except Exception as e:
        print(f"刪除檔案錯誤: {e}")


@app.route('/download', methods=['POST'])
def download():
    video_url = request.form.get('url')
    dl_type = request.form.get('type', 'video')
    if not video_url:
        return "請輸入影片網址"

    ydl_opts = {
        'noplaylist': True,
        'quiet': True,
    }

    if dl_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts['format'] = 'best[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info)

            if dl_type == 'audio':
                filename = os.path.splitext(filename)[0] + '.mp3'

            filename = os.path.abspath(filename)

            if not os.path.exists(filename):
                return "下載失敗：找不到檔案"

            # 啟動背景執行緒延遲刪除，避免檔案被占用刪除失敗
            threading.Thread(target=delayed_delete_file, args=(filename, 3600), daemon=True).start()

            return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))

    except Exception as e:
        return f"下載失敗: {e}"


if __name__ == '__main__':
    app.run(debug=True)
