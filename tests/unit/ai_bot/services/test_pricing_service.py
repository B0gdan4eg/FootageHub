"""
Unit тесты для PricingService.

Тестируем:
- Получение цен моделей
- Получение информации о моделях
- Конвертацию кредитов и USD
- Расчет стоимости
"""

from unittest.mock import AsyncMock, patch

import pytest

from ai_bot.services.pricing_service import PricingService


class TestPricingService:
    """Tests for PricingService"""

    def test_init_without_api_key(self):
        """Test initialization without API key"""
        service = PricingService()
        assert service._client is None

    def test_init_with_empty_api_key(self):
        """Test initialization with empty API key"""
        service = PricingService(api_key="")
        assert service._client is None

    def test_init_with_api_key(self):
        """Test initialization with API key"""
        with patch("ai_bot.services.pricing_service.KieAIClient"):
            service = PricingService(api_key="test-key")
            assert service._client is not None

    def test_get_model_price_success(self):
        """Test getting model price successfully"""
        service = PricingService()
        price = service.get_model_price("google/nano-banana")
        assert price == 4

    def test_get_model_price_unknown_model(self):
        """Test getting price for unknown model"""
        service = PricingService()
        with pytest.raises(ValueError, match="Unknown model"):
            service.get_model_price("unknown-model")

    def test_get_model_price_kling(self):
        """Test getting Kling model price"""
        service = PricingService()
        price = service.get_model_price("kling-2.6/text-to-video")
        assert price == 100

    def test_get_model_price_veo(self):
        """Test getting VEO model price"""
        service = PricingService()
        price_fast = service.get_model_price("veo-3.1/text-to-video")
        price_quality = service.get_model_price("veo-3.1/text-to-video-quality")
        assert price_fast == 80
        assert price_quality == 400

    def test_get_model_info_success(self):
        """Test getting model info successfully"""
        service = PricingService()
        info = service.get_model_info("google/nano-banana")
        assert info["name"] == "Nano Banana Pro"
        assert info["type"] == "image"
        assert info["credits"] == 4
        assert "description" in info

    def test_get_model_info_unknown_model(self):
        """Test getting info for unknown model"""
        service = PricingService()
        with pytest.raises(ValueError, match="Unknown model"):
            service.get_model_info("unknown-model")

    def test_get_all_models(self):
        """Test getting all models"""
        service = PricingService()
        models = service.get_all_models()
        assert len(models) > 0
        assert "google/nano-banana" in models
        assert "kling-2.6/text-to-video" in models
        assert "veo-3.1/text-to-video" in models

    def test_get_models_by_type_image(self):
        """Test getting image generation models"""
        service = PricingService()
        image_models = service.get_models_by_type("image")
        assert "google/nano-banana" in image_models
        assert "seedream-4.0" in image_models
        # Ensure no video models
        assert "kling-2.6/text-to-video" not in image_models

    def test_get_models_by_type_video(self):
        """Test getting video generation models"""
        service = PricingService()
        video_models = service.get_models_by_type("video")
        assert "kling-2.6/text-to-video" in video_models
        assert "veo-3.1/text-to-video" in video_models
        # Ensure no image models
        assert "google/nano-banana" not in video_models

    def test_get_models_by_type_empty(self):
        """Test getting models for non-existent type"""
        service = PricingService()
        audio_models = service.get_models_by_type("audio")
        assert len(audio_models) == 0

    @pytest.mark.asyncio
    async def test_get_kie_credits_no_client(self):
        """Test getting Kie credits when client is not initialized"""
        service = PricingService()
        credits = await service.get_kie_credits()
        assert credits is None

    @pytest.mark.asyncio
    async def test_get_kie_credits_with_client(self):
        """Test getting Kie credits with initialized client"""
        mock_client = AsyncMock()
        mock_client.get_account_credits.return_value = 1000

        service = PricingService()
        service._client = mock_client

        credits = await service.get_kie_credits()
        assert credits == 1000
        mock_client.get_account_credits.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_kie_credits_cached(self):
        """Test getting Kie credits from cache"""
        mock_client = AsyncMock()
        mock_client.get_account_credits.return_value = 1000

        service = PricingService()
        service._client = mock_client

        # First call
        credits1 = await service.get_kie_credits()
        # Second call (should use cache)
        credits2 = await service.get_kie_credits()

        assert credits1 == credits2 == 1000
        # Should only be called once due to caching
        mock_client.get_account_credits.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_kie_credits_force_refresh(self):
        """Test force refreshing Kie credits"""
        mock_client = AsyncMock()
        mock_client.get_account_credits.return_value = 1000

        service = PricingService()
        service._client = mock_client

        # First call
        await service.get_kie_credits()
        # Force refresh
        await service.get_kie_credits(force_refresh=True)

        # Should be called twice
        assert mock_client.get_account_credits.call_count == 2

    @pytest.mark.asyncio
    async def test_get_kie_credits_error_with_cache(self):
        """Test getting Kie credits on error with cached value"""
        mock_client = AsyncMock()
        mock_client.get_account_credits.side_effect = [1000, Exception("API Error")]

        service = PricingService()
        service._client = mock_client

        # First call succeeds
        credits1 = await service.get_kie_credits()
        assert credits1 == 1000

        # Second call fails but returns cached value
        credits2 = await service.get_kie_credits(force_refresh=True)
        assert credits2 == 1000

    def test_calculate_cost_single(self):
        """Test calculating cost for single generation"""
        service = PricingService()
        cost = service.calculate_cost("google/nano-banana", quantity=1)
        assert cost == 4

    def test_calculate_cost_multiple(self):
        """Test calculating cost for multiple generations"""
        service = PricingService()
        cost = service.calculate_cost("google/nano-banana", quantity=5)
        assert cost == 20

    def test_calculate_cost_video(self):
        """Test calculating cost for video generation"""
        service = PricingService()
        cost_kling = service.calculate_cost("kling-2.6/text-to-video", quantity=2)
        cost_veo = service.calculate_cost("veo-3.1/text-to-video", quantity=1)
        assert cost_kling == 200
        assert cost_veo == 80

    def test_credits_to_usd(self):
        """Test converting credits to USD"""
        service = PricingService()
        usd = service.credits_to_usd(100)
        assert usd == 0.5  # 100 * $0.005

    def test_credits_to_usd_none(self):
        """Test converting None credits to USD"""
        service = PricingService()
        usd = service.credits_to_usd(None)
        assert usd == 0.0

    def test_credits_to_usd_zero(self):
        """Test converting zero credits to USD"""
        service = PricingService()
        usd = service.credits_to_usd(0)
        assert usd == 0.0

    def test_usd_to_credits(self):
        """Test converting USD to credits"""
        service = PricingService()
        credits = service.usd_to_credits(1.0)
        assert credits == 200  # $1.0 / $0.005

    def test_usd_to_credits_small_amount(self):
        """Test converting small USD amount to credits"""
        service = PricingService()
        credits = service.usd_to_credits(0.02)
        assert credits == 4  # $0.02 / $0.005

    def test_credits_to_usd_roundtrip(self):
        """Test round-trip conversion credits -> USD -> credits"""
        service = PricingService()
        original_credits = 100
        usd = service.credits_to_usd(original_credits)
        back_to_credits = service.usd_to_credits(usd)
        assert back_to_credits == original_credits
