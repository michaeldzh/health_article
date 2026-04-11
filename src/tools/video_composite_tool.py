"""
视频合成工具
将多个分镜视频拼接成一个完整视频，并添加字幕和BGM
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
import json
import os
import tempfile
from typing import List, Dict, Optional

try:
    # 使用稳定的 moviepy.editor 导入路径
    from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip, concatenate_videoclips  # type: ignore
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


@tool
def composite_health_video(video_segments: str, bgm_url: str = "") -> str:
    """
    将多个分镜视频拼接成完整视频，并添加字幕和BGM

    Args:
        video_segments: 分镜视频信息JSON字符串，包含视频URL、字幕、时长等
        bgm_url: 背景音乐URL（可选）

    Returns:
        返回合成后的视频URL的JSON字符串
    """
    if not MOVIEPY_AVAILABLE:
        return json.dumps({
            "success": False,
            "error": "视频合成功能需要安装moviepy，请联系管理员安装"
        }, ensure_ascii=False)

    ctx = request_context.get() or new_context(method="composite_health_video")

    try:
        # 解析分镜视频数据
        segments = json.loads(video_segments)

        if not segments:
            return json.dumps({
                "success": False,
                "error": "没有提供分镜视频数据"
            }, ensure_ascii=False)

        # 创建临时目录
        temp_dir = tempfile.mkdtemp(prefix="video_composite_")
        print(f"临时目录: {temp_dir}")

        # 下载所有视频片段
        video_clips = []
        audio_clips = []
        subtitle_clips = []

        for i, segment in enumerate(segments):
            try:
                video_url = segment.get("video_url", "")
                subtitle_text = segment.get("subtitle", "")
                duration = segment.get("duration", 4)

                # 下载视频文件
                import requests
                video_response = requests.get(video_url, timeout=30)
                video_response.raise_for_status()

                video_path = os.path.join(temp_dir, f"segment_{i}.mp4")
                with open(video_path, 'wb') as f:
                    f.write(video_response.content)

                # 加载视频片段
                clip = VideoFileClip(video_path)
                if duration > 0 and clip.duration > duration:
                    clip = clip.subclip(0, duration)
                video_clips.append(clip)

                # 添加字幕
                if subtitle_text:
                    try:
                        txt_clip = TextClip(
                            subtitle_text,
                            fontsize=32,
                            color='white',
                            font='SimHei',  # 使用黑体支持中文
                            stroke_color='black',
                            stroke_width=2,
                            size=(clip.w * 0.9, None),
                            method='caption'
                        ).set_position(('center', 'bottom')).set_duration(clip.duration)
                        subtitle_clips.append(txt_clip)
                    except Exception as e:
                        print(f"字幕生成失败: {str(e)}")
                        # 如果中文字幕失败，尝试使用英文
                        try:
                            txt_clip = TextClip(
                                subtitle_text,
                                fontsize=32,
                                color='white',
                                stroke_color='black',
                                stroke_width=2,
                                size=(clip.w * 0.9, None),
                                method='caption'
                            ).set_position(('center', 'bottom')).set_duration(clip.duration)
                            subtitle_clips.append(txt_clip)
                        except:
                            pass

                print(f"场景 {i+1} 处理完成")

            except Exception as e:
                print(f"场景 {i+1} 处理失败: {str(e)}")
                continue

        if not video_clips:
            return json.dumps({
                "success": False,
                "error": "没有成功加载任何视频片段"
            }, ensure_ascii=False)

        # 拼接视频
        final_video = concatenate_videoclips(video_clips, method="compose")

        # 添加字幕到视频上
        if subtitle_clips:
            # 确保字幕和视频片段一一对应
            matched_subtitles = subtitle_clips[:len(video_clips)]
            videos_with_subtitles = []
            for video, subtitle in zip(video_clips, matched_subtitles):
                composite = CompositeVideoClip([video, subtitle])
                videos_with_subtitles.append(composite)
            final_video = concatenate_videoclips(videos_with_subtitles, method="compose")

        # 添加BGM
        if bgm_url:
            try:
                # 下载BGM
                bgm_response = requests.get(bgm_url, timeout=30)
                bgm_response.raise_for_status()

                bgm_path = os.path.join(temp_dir, "bgm.mp3")
                with open(bgm_path, 'wb') as f:
                    f.write(bgm_response.content)

                # 加载BGM并调整长度
                bgm = AudioFileClip(bgm_path)
                if bgm.duration > final_video.duration:
                    bgm = bgm.subclip(0, final_video.duration)
                elif bgm.duration < final_video.duration:
                    # 循环BGM
                    bgm = bgm.loop(duration=final_video.duration)

                # 降低BGM音量，不影响旁白
                bgm = bgm.volumex(0.3)

                # 如果原视频有音频，混合音频
                if final_video.audio:
                    final_audio = final_video.audio
                    mixed_audio = final_audio.overlay(bgm)
                    final_video = final_video.set_audio(mixed_audio)
                else:
                    final_video = final_video.set_audio(bgm)

                print("BGM添加完成")

            except Exception as e:
                print(f"BGM添加失败: {str(e)}")

        # 输出视频到临时文件
        output_path = os.path.join(temp_dir, "final_video.mp4")
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile=os.path.join(temp_dir, "temp_audio.m4a"),
            remove_temp=True,
            fps=24,
            verbose=False,
            logger=None
        )

        print(f"视频合成完成: {output_path}")

        # 清理临时文件
        final_video.close()
        for clip in video_clips:
            clip.close()
        for clip in subtitle_clips:
            clip.close()
        if 'bgm' in locals():
            bgm.close()

        return json.dumps({
            "success": True,
            "data": {
                "video_path": output_path,
                "duration": final_video.duration,
                "fps": final_video.fps,
                "resolution": f"{int(final_video.w)}x{int(final_video.h)}",
                "segments_count": len(segments)
            },
            "message": f"成功合成视频，总时长：{final_video.duration:.2f}秒"
        }, ensure_ascii=False)

    except json.JSONDecodeError as e:
        return json.dumps({
            "success": False,
            "error": f"分镜视频数据格式不正确：{str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return json.dumps({
            "success": False,
            "error": f"视频合成失败：{str(e)}"
        }, ensure_ascii=False)
