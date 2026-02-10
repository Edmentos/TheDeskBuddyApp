# Posture Detection

Simple sitting/standing detection based on desk height with spike filtering.

## How It Works

1. **Set Your Sitting Height**: In the Settings page, enter your typical sitting desk height (e.g., 80cm)
2. **Standing Detection**: The system adds 10cm (configurable) to determine when you're standing
3. **Spike Filtering**: Uses a 5-sample moving average to ignore sensor spikes

## Example

If you set sitting height to **80cm** with a **10cm offset**:
- **Sitting**: Distance < 90cm
- **Standing**: Distance ≥ 90cm

If the ultrasonic sensor briefly reads 110cm for 1 second (spike), the moving average smooths it out and prevents false detection.

## API Endpoints

### Get Settings
```http
GET /settings/posture
```

Response:
```json
{
  "sitting_height_cm": 80.0,
  "standing_offset_cm": 10.0,
  "standing_threshold_cm": 90.0,
  "current_state": "sitting",
  "smoothed_distance_cm": 78.5
}
```

### Update Settings
```http
PUT /settings/posture
Content-Type: application/json

{
  "sitting_height_cm": 80.0,
  "standing_offset_cm": 10.0
}
```

## Database

Posture state is saved as a sensor reading:
- `sensor='posture'`
- `value=1.0` for standing, `value=0.0` for sitting
- `unit='sitting'` or `unit='standing'`

## Frontend

Go to **Settings** page to configure your desk height. The current posture state is displayed at the top.
