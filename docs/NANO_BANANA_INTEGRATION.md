# NANO BANANA Integration via Kie.ai

## Overview

Integration of Google's NANO BANANA image generation model through the Kie.ai API. This feature allows managers to test AI image generation directly from the Telegram bot manager panel.

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# Kie.ai API configuration
KIE_AI_API_KEY=your_api_key_here
```

Get your API key from: https://kie.ai/api-key

### Files Modified

1. **bot/config.py** - Added `KIE_AI_API_KEY` configuration
2. **bot/state.py** - Added FSM states for NANO BANANA workflow:
   - `ManagerFlow.waiting_for_prompt`
   - `ManagerFlow.waiting_for_aspect_ratio`
   - `ManagerFlow.waiting_for_resolution`
   - `ManagerFlow.waiting_for_output_format`

### New Files

**bot/kie_utils.py** - Complete Kie.ai API client implementation with:
- `KieAIClient` class for API interactions
- Task creation and status polling
- Automatic result retrieval
- Error handling and timeouts

## Usage

### From Manager Panel

1. Open manager panel: `/manager`
2. Click "🍌 Тест NANO BANANA"
3. Enter a text prompt (e.g., "A surreal painting of a giant banana floating in space")
4. Configure generation parameters:
   - **Aspect Ratio**: 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, auto
   - **Resolution**: 1K, 2K, 4K
   - **Output Format**: PNG, JPG
5. Click "✅ Генерировать"
6. Wait for image generation (typically 30-120 seconds)
7. Receive generated image with URL

### Programmatic Usage

```python
from bot.kie_utils import get_kie_client

# Get client
kie_client = get_kie_client()

# Generate image (simple method)
image_url = await kie_client.generate_image(
    prompt="A beautiful sunset over mountains",
    aspect_ratio="16:9",
    resolution="4K",
    output_format="png",
    timeout=300
)

# Advanced: Create task and poll manually
result = await kie_client.create_task(
    prompt="A futuristic city",
    aspect_ratio="21:9",
    resolution="4K",
    output_format="jpg"
)

task_id = result["data"]["taskId"]

# Wait for completion
final_result = await kie_client.wait_for_completion(
    task_id=task_id,
    timeout=300,
    poll_interval=3
)
```

## API Details

### Supported Parameters

| Parameter | Type | Options | Default | Required |
|-----------|------|---------|---------|----------|
| `prompt` | string | Any text description | - | Yes |
| `aspect_ratio` | string | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, auto | 1:1 | No |
| `resolution` | string | 1K, 2K, 4K | 2K | No |
| `output_format` | string | png, jpg | png | No |
| `image_input` | array | URLs of input images | null | No |

### Polling Strategy

The client uses adaptive polling intervals:
- **0-30 seconds**: Poll every 2 seconds
- **30-120 seconds**: Poll every 5 seconds
- **120+ seconds**: Poll every 10 seconds
- **Max timeout**: 300 seconds (5 minutes) by default

### Error Handling

Common error codes from Kie.ai API:
- `401`: Unauthorized (invalid API key)
- `402`: Insufficient credits
- `404`: Not found
- `422`: Validation error (invalid parameters)
- `429`: Rate limited
- `455`: Service maintenance
- `500`: Server error
- `501`: Generation failed

## Manager Panel Handlers

### Handler Flow

1. **manager_test_nano_banana** - Entry point, initializes config
2. **receive_nano_prompt** - Receives prompt text, shows config menu
3. **config_aspect_ratio** - Shows aspect ratio selection
4. **set_aspect_ratio** - Saves selected aspect ratio
5. **config_resolution** - Shows resolution selection
6. **set_resolution** - Saves selected resolution
7. **config_format** - Shows format selection
8. **set_format** - Saves selected format
9. **show_config_menu** - Displays current configuration
10. **generate_nano_banana** - Executes generation and returns image
11. **cancel_nano_banana** - Cancels the process

### State Management

All configuration is stored in FSM context:
```python
{
    "prompt": "user's text prompt",
    "aspect_ratio": "16:9",
    "resolution": "4K",
    "output_format": "png"
}
```

## Integration Points

The NANO BANANA feature is fully integrated into the manager panel alongside:
- Statistics (`admin_stats`)
- Database export (`export_db`)
- Referral management
- Browser restarts (Envato/Freepik)
- WebPay testing

## Future Enhancements

Possible improvements:
1. Add `image_input` support for image editing mode
2. Store generation history in database
3. Add batch generation capability
4. Integrate with user-facing features (subscription-based)
5. Add style presets (realistic, artistic, cartoon, etc.)
6. Support for NANO BANANA Edit model (image-to-image)

## Troubleshooting

### "KIE_AI_API_KEY is not set"
- Ensure `.env` file contains `KIE_AI_API_KEY=your_key`
- Restart the bot after adding the key

### "Task timed out"
- Default timeout is 300 seconds
- Increase timeout in `generate_image()` call if needed
- Check Kie.ai service status

### "Insufficient credits" (402 error)
- Add credits to your Kie.ai account
- Check balance at https://kie.ai/

### "Invalid API key" (401 error)
- Verify API key is correct
- Generate new key at https://kie.ai/api-key

## Documentation References

- Kie.ai API Docs: https://docs.kie.ai/
- NANO BANANA Model: https://docs.kie.ai/market/google/nano-banana
- Get Task Details: https://docs.kie.ai/market/common/get-task-detail
