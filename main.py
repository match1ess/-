import os
import json
import time
import requests
import tempfile
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import subprocess

class VideoPipeline:
    def __init__(self):
        self.tmp_dir = "/tmp"
        self.feishu_webhook = os.getenv("FEISHU_WEBHOOK")
        self.asr_key = os.getenv("ASR_API_KEY")
        self.asr_secret = os.getenv("ASR_API_SECRET")
        
    def download_video(self, url, filename="input.mp4"):
        """下载视频到本地"""
        local_path = os.path.join(self.tmp_dir, filename)
        r = requests.get(url, stream=True)
        r.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path

    def cut_video(self, input_path, start, end):
        """精准剪辑视频片段"""
        output_path = os.path.join(self.tmp_dir, "cut.mp4")
        
        # 使用 FFmpeg 快速剪辑（避免重新编码）
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-ss", str(start), "-t", str(end - start),
            "-c", "copy",  # 直接复制流，不重新编码（极快）
            "-avoid_negative_ts", "make_zero",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    def extract_audio(self, video_path):
        """提取音频用于识别"""
        audio_path = os.path.join(self.tmp_dir, "audio.wav")
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            audio_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return audio_path

    def generate_subtitles(self, audio_path):
        """
        生成字幕（使用阿里云语音转写 API）
        如需免费方案，可替换为本地 Whisper tiny
        """
        try:
            # 这里示例使用阿里云语音转写
            # 实际使用时替换为你的 ASR 服务调用
            upload_url = "https://your-asr-service.com/upload"
            
            with open(audio_path, 'rb') as f:
                files = {'file': ('audio.wav', f, 'audio/wav')}
                headers = {'Authorization': f'Bearer {self.asr_key}'}
                resp = requests.post(upload_url, files=files, headers=headers, timeout=30)
                
            result = resp.json()
            return result.get("subtitles", [])  # 返回 [(start, end, text), ...]
            
        except Exception as e:
            print(f"字幕生成失败: {e}")
            return []  # 失败时返回空列表，不影响主流程

    def create_cover(self, title, subtitle=""):
        """生成品牌化封面（头等大事徐峰风格）"""
        width, height = 1080, 1920
        
        # 创建深色渐变背景
        img = Image.new('RGB', (width, height), color='#0f0f23')
        draw = ImageDraw.Draw(img)
        
        # 添加装饰线条（品牌视觉元素）
        draw.line([(100, 600), (980, 600)], fill="#4a90e2", width=8)
        draw.line([(100, 1300), (980, 1300)], fill="#4a90e2", width=4)
        
        # 字体（使用系统默认字体，如需定制可上传字体文件到 assets）
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
            sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
            brand_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            title_font = ImageFont.load_default()
            sub_font = ImageFont.load_default()
            brand_font = ImageFont.load_default()
        
        # 主标题（居中）
        bbox = draw.textbbox((0, 0), title, font=title_font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) / 2
        draw.text((x, 800), title, fill="#ffffff", font=title_font)
        
        # 副标题
        if subtitle:
            bbox2 = draw.textbbox((0, 0), subtitle, font=sub_font)
            text_width2 = bbox2[2] - bbox2[0]
            x2 = (width - text_width2) / 2
            draw.text((x2, 950), subtitle, fill="#cccccc", font=sub_font)
        
        # 品牌标识（底部）
        draw.text((width/2, 1700), "@头等大事徐峰", fill="#4a90e2", font=brand_font, anchor="mm")
        draw.text((width/2, 1760), "养发干货·科学防脱", fill="#666666", font=sub_font, anchor="mm")
        
        cover_path = os.path.join(self.tmp_dir, "cover.jpg")
        img.save(cover_path, quality=95)
        return cover_path

    def burn_subtitles(self, video_path, subtitles):
        """将字幕烧录到视频（硬字幕）"""
        if not subtitles:
            return video_path
            
        # 生成 ASS 字幕文件（样式可自定义）
        ass_path = os.path.join(self.tmp_dir, "subs.ass")
        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write(self._generate_ass_header())
            for start, end, text in subtitles:
                f.write(f"Dialogue: 0,{self._sec_to_ass(start)},{self._sec_to_ass(end)},Default,,0,0,0,,{text}\n")
        
        output_path = os.path.join(self.tmp_dir, "with_subs.mp4")
        
        # 使用 FFmpeg 烧录字幕
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"ass={ass_path}",
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path

    def _generate_ass_header(self):
        """ASS 字幕文件头（样式配置）"""
        return """[Script Info]
Title: Auto Generated
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,100,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def _sec_to_ass(self, seconds):
        """秒数转 ASS 时间格式"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    def add_cover_and_tail(self, video_path, cover_path, duration=3):
        """添加封面片头（3秒）+ 片尾关注引导"""
        video = VideoFileClip(video_path)
        
        # 封面片头
        cover = ImageClip(cover_path).set_duration(duration).resize(height=1920)
        
        # 片尾（可选）
        tail_duration = 2
        tail_img = Image.new('RGB', (1080, 1920), '#0f0f23')
        tail_draw = ImageDraw.Draw(tail_img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        except:
            font = ImageFont.load_default()
        tail_draw.text((540, 960), "关注峰哥\n拯救发际线", fill="white", font=font, anchor="mm", align="center")
        tail = ImageClip(tail_img).set_duration(tail_duration)
        
        # 合成
        final = concatenate_videoclips([cover, video, tail])
        output_path = os.path.join(self.tmp_dir, "final.mp4")
        final.write_videofile(output_path, codec="libx264", fps=30, threads=4)
        
        video.close()
        return output_path

    def upload_to_cloud(self, local_path):
        """上传到云存储（示例：阿里云 OSS）"""
        # 这里替换为你的实际上传逻辑
        # 返回可访问的 URL
        filename = f"output_{int(time.time())}.mp4"
        # TODO: 实现实际上传
        return f"https://your-bucket.oss-cn-beijing.aliyuncs.com/{filename}"

    def notify_feishu(self, video_url, metadata):
        """发送飞书卡片消息"""
        if not self.feishu_webhook:
            print("未配置飞书 Webhook，跳过通知")
            return
            
        message = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🎬 视频剪辑完成"
                    },
                    "template": "blue"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**标题**：{metadata.get('title', '未命名')}\n**时长**：{metadata.get('duration', 0):.1f}秒\n**字幕**：{'已生成' if metadata.get('has_subs') else '无字幕'}"
                        }
                    },
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {
                                    "tag": "plain_text",
                                    "content": "下载视频"
                                },
                                "type": "primary",
                                "url": video_url
                            }
                        ]
                    }
                ]
            }
        }
        
        resp = requests.post(self.feishu_webhook, json=message)
        resp.raise_for_status()
        return resp.json()

def handler(event, context):
    """
    KimiClaw 入口函数
    触发方式：HTTP POST /process
    Body: {
        "video_url": "http://example.com/input.mp4",
        "cut_start": 5,
        "cut_end": 35,
        "cover_title": "3招拯救发际线",
        "cover_subtitle": "实测有效"
    }
    """
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 获取参数（支持环境变量兜底）
        video_url = body.get('video_url') or os.getenv('VIDEO_URL')
        cut_start = float(body.get('cut_start', os.getenv('CUT_START', 0)))
        cut_end = float(body.get('cut_end', os.getenv('CUT_END', 60)))
        cover_title = body.get('cover_title') or os.getenv('COVER_TITLE', '今日养发干货')
        cover_subtitle = body.get('cover_subtitle') or os.getenv('COVER_SUBTITLE', '')
        
        if not video_url:
            return {"statusCode": 400, "body": "缺少视频 URL"}
            
        pipeline = VideoPipeline()
        
        # Step 1: 下载
        print("正在下载视频...")
        local_video = pipeline.download_video(video_url)
        
        # Step 2: 剪辑
        print(f"剪辑视频 {cut_start}s - {cut_end}s...")
        cut_video = pipeline.cut_video(local_video, cut_start, cut_end)
        
        # Step 3: 提取音频 & 生成字幕（可选）
        print("生成字幕...")
        audio_path = pipeline.extract_audio(cut_video)
        subtitles = pipeline.generate_subtitles(audio_path)
        video_with_subs = pipeline.burn_subtitles(cut_video, subtitles)
        
        # Step 4: 生成封面
        print("生成品牌封面...")
        cover_path = pipeline.create_cover(cover_title, cover_subtitle)
        
        # Step 5: 合成最终视频
        print("合成最终视频...")
        final_video = pipeline.add_cover_and_tail(video_with_subs, cover_path)
        
        # Step 6: 上传（实际使用时配置你的云存储）
        print("上传视频...")
        # video_url = pipeline.upload_to_cloud(final_video)
        video_url = "https://placeholder-for-your-cdn.com/video.mp4"
        
        # Step 7: 飞书通知
        metadata = {
            "title": cover_title,
            "duration": cut_end - cut_start + 5,  # +片头片尾
            "has_subs": len(subtitles) > 0
        }
        pipeline.notify_feishu(video_url, metadata)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "video_url": video_url,
                "duration": metadata['duration'],
                "subtitles_count": len(subtitles)
            }, ensure_ascii=False)
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"处理失败: {error_msg}")
        
        # 错误通知飞书
        if os.getenv("FEISHU_WEBHOOK"):
            requests.post(os.getenv("FEISHU_WEBHOOK"), json={
                "msg_type": "text",
                "content": {"text": f"❌ 视频处理失败：{error_msg}"}
            })
            
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_msg})
        }