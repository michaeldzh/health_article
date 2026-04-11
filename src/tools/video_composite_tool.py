"""
视频合成工具
将多个分镜视频拼接成一个完整视频，并添加字幕和BGM
适配 MoviePy 2.2.1 新 API
"""
from langchain.tools import tool
from coze_coding_utils.log.write_log import request_context
from coze_coding_utils.runtime_ctx.context import new_context
import json
import os
import tempfile
from typing import List, Dict, Optional

try:
    # MoviePy 2.2.1 新的导入方式
    from moviepy import (
        VideoFileClip,
        TextClip,
        CompositeVideoClip,
        AudioFileClip,
        CompositeAudioClip,
        concatenate_videoclips
    )
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

                # MoviePy 2.2.1: 使用 with_section 或 with_end 来裁剪视频
                if duration > 0 and clip.duration > duration:
                    clip = clip.with_end(duration)

                video_clips.append(clip)

                # 添加字幕
                if subtitle_text:
                    try:
                        # 尝试使用中文字体
                        txt_clip = TextClip(
                            subtitle_text,
                            fontsize=32,
                            color='white',
                            font='SimHei',  # 使用黑体支持中文
                            stroke_color='black',
                            stroke_width=2,
                            size=(clip.w * 0.9, None),
                            method='caption'
                        )
                        # MoviePy 2.2.1: 使用 with_position 和 with_duration
                        txt_clip = txt_clip.with_position(('center', 'bottom')).with_duration(clip.duration)
                        subtitle_clips.append(txt_clip)
                    except Exception as e:
                        print(f"中文字幕生成失败: {str(e)}")
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
                            )
                            txt_clip = txt_clip.with_position(('center', 'bottom')).with_duration(clip.duration)
                            subtitle_clips.append(txt_clip)
                        except Exception as e2:
                            print(f"字幕生成完全失败: {str(e2)}")
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

        # 拼接视频 - MoviePy 2.2.1
        # 先为每个视频片段添加对应的字幕
        videos_with_subtitles = []
        for i, video in enumerate(video_clips):
            if i < len(subtitle_clips):
                # MoviePy 2.2.1: 使用 CompositeVideoClip 直接合成
                composite = CompositeVideoClip([video, subtitle_clips[i]])
                videos_with_subtitles.append(composite)
            else:
                videos_with_subtitles.append(video)

        # 拼接所有视频片段
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

                # 加载BGM并调整长度 - MoviePy 2.2.1
                bgm = AudioFileClip(bgm_path)
                if bgm.duration > final_video.duration:
                    bgm = bgm.with_end(final_video.duration)
                elif bgm.duration < final_video.duration:
                    # 手动循环BGM - 计算需要循环的次数
                    loops_needed = int(final_video.duration / bgm.duration) + 1
                    # 创建多个BGM副本并拼接
                    bgm_clips = [bgm] * loops_needed
                    from moviepy import concatenate_audioclips
                    bgm = concatenate_audioclips(bgm_clips).with_end(final_video.duration)

                # 降低BGM音量 - MoviePy 2.2.1 使用 with_volume_scaled
                bgm = bgm.with_volume_scaled(0.3)

                # 如果原视频有音频，混合音频
                if final_video.audio:
                    final_audio = final_video.audio
                    # MoviePy 2.2.1: 使用 CompositeAudioClip
                    mixed_audio = CompositeAudioClip([final_audio, bgm])
                    final_video = final_video.with_audio(mixed_audio)
                else:
                    final_video = final_video.with_audio(bgm)

                print("BGM添加完成")

            except Exception as e:
                print(f"BGM添加失败: {str(e)}")

        # 输出视频到临时文件
        output_path = os.path.join(temp_dir, "final_video.mp4")

        # MoviePy 2.2.1: write_videofile 方法参数可能不同
        # 设置 fps - MoviePy 2.2.1 使用 with_fps 方法
        final_video = final_video.with_fps(24)

        # 获取视频信息
        video_duration = getattr(final_video, 'duration', 0)
        video_w = getattr(final_video, 'w', 0)
        video_h = getattr(final_video, 'h', 0)

        # 写入视频文件
        final_video.write_videofile(  # type: ignore
            output_path,
            codec='libx264',
            audio_codec='aac',
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
                "duration": video_duration,
                "resolution": f"{int(video_w)}x{int(video_h)}",
                "segments_count": len(segments)
            },
            "message": f"成功合成视频，总时长：{video_duration:.2f}秒"
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
