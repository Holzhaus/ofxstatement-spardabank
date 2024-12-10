# Sparda-Bank plugin for ofxstatement

This plugin adds support for parsing CSV files from the regional variants of
Sparda-Bank eG.

## Supported Banks

| Country | Bank                          | BLZ      | BIC         |
| ------- | ----------------------------- | -------- | ----------- |
| DE      | Sparda-Bank Nürnberg          | 76090500 | GENODEF1S06 |
| DE      | Sparda-Bank Ostbayern         | 75090500 | GENODEF1S05 |
| DE      | Sparda-Bank Berlin            | 12096597 | GENODEF1S10 |
| DE      | Sparda-Bank Hamburg           | 20690500 | GENODEF1S11 |
| DE      | Sparda-Bank Hannover          | 25090500 | GENODEF1S09 |
| DE      | Sparda-Bank West              | 33060592 | GENODED1SPW |
| DE      | Sparda-Bank West              | 36060591 | GENODED1SPE |
| DE      | Sparda-Bank West              | 37060590 | GENODED1SPK |
| DE      | Sparda-Bank West              | 40060560 | GENODEF1S08 |
| DE      | Sparda-Bank Hessen            | 50090500 | GENODEF1S12 |
| DE      | Sparda-Bank Südwest           | 55090500 | GENODEF1S01 |
| DE      | Sparda-Bank Baden-Württemberg | 60090800 | GENODEF1S02 |
| DE      | Sparda-Bank München           | 70090500 | GENODEF1S04 |
| DE      | Sparda-Bank Augsburg          | 72090500 | GENODEF1S03 |

## Configuration

To make this plugin work correctly, you need to configure your bank's BIC.
After installation, run the following command:

```bash
ofxstatement edit-config
```

The config file will be opened in the editor. Add

```ini
[spardabank]
plugin = spardabank
bic = <your bic>
```

To find the BIC for your bank, check the online banking portal, the back of
your debit card or use one of the BICs from the table above.
