# ThronesBot
A Python based Game of Thrones LCG 2nd Edition chat bot for the Slack messaging service.

Functions:

- Search and display the details of a card: [[Card name]]
- If multiple cards of the same name, define pack code: [[Card Name:Pack Code]] ie [[Eddard Stark:WotN]]
- Supports substring searches ie [[eddard:core]]
- Display the latest pack release status from FFG: [[pack status]]
- Display all cards in a pack: [[pack:Pack Code]] ie [[pack:TtB]]

All commands are case in-sensitive

Pre-requisits:
- Python 3 environment (or later)
- SlackClient python package (pip install slackclient)

To run:
- Insert your slack token at the bottom of the script (TODO: make config file for this)
- Run the script with python 3 or later



Much thanks to:
- ThronesDB for their awesome API https://github.com/Alsciende/thronesdb
- SlackClient https://github.com/slackhq/python-slackclient
- All my pedantic testers
