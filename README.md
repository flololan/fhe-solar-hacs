# FHE Solar for Home Assistant

Custom integration that brings the photovoltaic data of an **FHE** home (FHE Master 1000 micro-inverters)
into Home Assistant, using the same cloud account as the *FHE Solar* app.

<!-- ha-marketplace:exclude-start -->
## Installation

[![Open your Home Assistant instance and open a repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=flololan&repository=fhe-solar-hacs&category=integration)

1. Open the repository in the Home Assistant **Marketplace** with the button above and install it.
2. Restart Home Assistant.
3. Add the integration:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=fhe_solar)

Manual installation: copy `custom_components/fhe_solar` into the `custom_components` folder of your
Home Assistant configuration and restart.
<!-- ha-marketplace:exclude-end -->

## Configuration

The UI texts are available in English, German and French.

The integration is configured from the UI (**Settings → Devices & services → Add integration → FHE Solar**).
Enter the e-mail address and password of your FHE Solar account. The integration signs in, stores the
returned API token together with the credentials, and uses the home linked to the account.

If the API rejects the token, the integration signs in again with the stored credentials. Only when that
fails too, Home Assistant asks you to re-authenticate.

## Devices and entities

One device per inverter (`FHE Master 1000`) and one device for the home (`FHE Home`).

| Device | Entity | Unit | State class |
|---|---|---|---|
| Inverter | Output power | kW | measurement |
| Inverter | PV1 power | kW | measurement |
| Inverter | PV2 power | kW | measurement |
| Inverter | Today yield | kWh | total_increasing |
| Home | Total power | kW | measurement |
| Home | Total today yield | kWh | total_increasing |

**Total today yield** is the entity intended for the Energy dashboard (solar production).

### Notes on "today yield"

The cloud API reports the energy of the current day per inverter. Inverters have been observed to disappear
from the live data in the evening, and a single inverter has been observed to report `0.0` again on the same
day. To keep the
`total_increasing` sensors consistent, the integration keeps the highest value seen per inverter for the
current (local) day and sums those values for the home. The values are reset at the local day change and
restored after a Home Assistant restart if they were written on the same day.

## Polling

The integration polls the cloud API with an adaptive interval:

- every 30 s while live data is available,
- backing off from 30 min up to 60 min when no live data is returned (for example at night),
- at least 30 min while the sun is below the horizon (`sun.sun` elevation ≤ 0; fallback 07–19 h local time
  if the sun integration is not available).

## Diagnostics

Diagnostics can be downloaded from the config entry. Credentials, the API token, names, e-mail addresses,
phone numbers, the home address and inverter serial numbers are redacted.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by FHE. It uses the cloud API behind the
FHE Solar app (`api.fhe.fhe-france.fr`); no public documentation of that API is known to the author, and
it may change or stop working without notice. Use at your own risk.

## Issues

Please report problems via the
[issue tracker](https://github.com/flololan/fhe-solar-hacs/issues) and attach the diagnostics file.

## License

GPL-3.0 – see [LICENSE](LICENSE).

The brand icon (`custom_components/fhe_solar/brand/`, source in `assets/icon.svg`) is original artwork made for
this project (generic sun and solar panel) and is licensed under the same license. It is not the FHE logo.
