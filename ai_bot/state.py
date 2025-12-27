"""
AI Bot States

FSM states for AI Bot conversations
"""
from aiogram.fsm.state import State, StatesGroup


class ImageGenerationStates(StatesGroup):
    """States for image generation flow"""
    waiting_for_prompt = State()
    waiting_for_aspect_ratio = State()
    waiting_for_resolution = State()
    waiting_for_reference_image = State()  # For image editing
    processing = State()


class VideoGenerationStates(StatesGroup):
    """States for video generation flow"""
    waiting_for_provider_choice = State()  # Kling or VEO
    waiting_for_prompt = State()
    waiting_for_aspect_ratio = State()
    waiting_for_duration = State()
    waiting_for_reference_image = State()  # For image-to-video
    waiting_for_sound_option = State()  # Kling only
    processing = State()
