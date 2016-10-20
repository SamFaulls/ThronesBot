import sys
sys.dont_write_bytecode = True

import os
import json
import time
import re
import urllib.request
import traceback
from slackclient import SlackClient

class slackBot(object):
    ''' Main slackbot class, contains generic methods for connecting, reading and
    writing data using slack RTM API '''
    
    def __init__(self, token):
        ''' Constructor, sets channel to monitor, connection token to use and defines
        the user image for the bot'''
        self.channel = 'thrones'
        self.token = token
        self.outputList = []
        self.lastPing = 0
        self.icon = 'https://images-cdn.fantasyflightgames.com/filer_public/63/44/63440b92-6adc-45b8-8bf3-6d30565062c2/gt01_challengeicons_power.png'

    def connect(self):
        ''' Uses given token to connect to the Slack RTM API '''
        self.sc = SlackClient(token)
        result = self.sc.rtm_connect()
        print("Connection state", result)
        return result

    def start(self):
        ''' Starts the main loop '''
        self.connect()
        # Initialise Thrones specific 'plugin'
        self.thronesBot = thronesPlugin(self)
        # Main loop to read/write to channel
        while True:
            try:
                for reply in self.sc.rtm_read():
                    self.read(reply)
                    self.write()
                    self.ping()
                    time.sleep(1)
            except:
                connect = False
                while not connect:
                    connect = self.connect()
                self.start()
                    

    def read(self, data):
        ''' Sends data read from the channel to be processed '''
        if "type" in data and data["type"] == "message":
            try:
                self.processMessage(data)
            except:
                print('Error happened lol I can\'t Python', sys.exc_info(), traceback.print_tb(sys.exc_info()[2]))

    def write(self):
        ''' Posts messages from the queue to the channel, including any attachments''' 
        pause = False
        for output in self.outputList:
            sendChannel = self.sc.server.channels.find(output[0])
            if sendChannel == output[0] and output[1] != None:
                if pause == True:
                    time.sleep(.1)
                    pause = False
                message = output[1]
                print('sending', message, 'on channel', output[0])
                result = self.sc.api_call("chat.postMessage",
                                          channel='#' + output[0],
                                          text=message,
                                          attachments=json.dumps(output[2]),
                                          username="ThronesBot",
                                          icon_url=self.icon)
                                          
                print(result)                          
                pause = True
            else:
                print('failed to send message', output[1], 'to channel', sendChannel)
            self.outputList.remove(output)

    def ping(self):
        currentTime = int(time.time())
        if currentTime > self.lastPing + 5:
            result = self.sc.server.ping()
            self.lastPing = currentTime
            if result == False:
                self.connect()
                self.ping()
    

    def processMessage(self, data):
        if "text" in data:
            message = data["text"]
            pattern = re.compile("\[\[([^\.].*?)\]\]")
            match = pattern.search(message)
            if match:
                commands = match.groups()
                for command in commands:
                    self.thronesBot.processMessage(command)

    def queueResponse(self, message, attachment=None):
        if message != None:
            self.outputList.append([self.channel, message, attachment])

class thronesPlugin(object):

    def __init__(self, slackBot):
        self.slackBot = slackBot
        self.helpMessage = '''To use me, type commands in double square brackets (i.e. [[...]] ). 
                            You can type the name of a card to see it, or request the upcoming release statuses 
                            with "Pack Status"'''
        
        
        cardsPage = urllib.request.urlopen('http://thronesdb.com/api/public/cards').read()
        cardsText = cardsPage.decode('ascii')
        self.cardsList = json.loads(cardsText)

        url = 'https://www.fantasyflightgames.com/en/upcoming/'
        self.urlRequest = urllib.request.Request(url, headers={'User-Agent' : 'Magic Browser'})

        
        self.buildColourMap()

        
    def processMessage(self, message):
        ''' Takes messages from the slack bot and sends them for 
            specific processing'''
        
        # List of distinct functions to be evaluated in turn
        # Note: processCard should be last as a 'default'
        functionList = ['processPackStatus', 'processPackList', 'processHelp', 'processCard']
        
        for function in functionList:
            match = eval("self." + function)(message)
            if match: break

    def processCard(self, message):
        ''' Process message as a card request'''
        # Split message if pack code is also given
        deconstMessage = message.split(':')
        cardName = deconstMessage[0]
        attachment = None
        # If pack code is given, find card by pack, else search on just name
        if len(deconstMessage) > 1:
            packName = deconstMessage[1]
            cardMatch = self.findCardByPack(cardName, packName)
        else:
            cardMatch = self.findCardByCardName(cardName)
            
        # If a single card is found, build and send the response
        # Else if multiple cards are found, prompt user to refine search
        if cardMatch != None and len(cardMatch) == 1:
            try:
                response = ""
                attachment = self.buildCardResponse(cardMatch[0])
            except:
                response = "Can't process that, sorry Sam can't code"
        elif cardMatch != None and 1 < len(cardMatch) < 15:
            response = 'Multiple cards were found with that name: \n'
            for card in cardMatch:
                response = response + '\n' + card['name'] + ' - ' + card['pack_code']
        # If too many cards are returned, do not bother displaying them all
        elif cardMatch != None and len(cardMatch) > 14:
            response = "Too many cards were returned, please narrow your search"
        else:
            response = "Sorry, I can't find that card"
            
        slackBot.queueResponse(self.slackBot, response, attachment)
        
    def findCardByCardName(self, cardName):
        print('Looking for', cardName)

        cardMatches = []
        # Loop through list of cards for requested card name.
        # If exact match is found, break immediately otherwise do substring
        # searching, adding any matches to the list
        for card in self.cardsList:
            if cardName.lower() == card['name'].lower():
                cardMatches = [card]
                break
            elif cardName.lower() in card['name'].lower():
                cardMatches.append(card)
        
        return cardMatches

    def findCardByPack(self, cardName, packName):
        print('Looking for', cardName, packName)
        
        cardMatches = []
        for card in self.cardsList:
            if cardName.lower() == card['name'].lower() and card['pack_code'].lower() == packName.lower():
                cardMatches.append(card)
                break
            elif cardName.lower() in card['name'].lower() and card['pack_code'].lower() == packName.lower():
                cardMatches.append(card)
                
        return cardMatches
            

    def processPackStatus(self, message):
        ''' Method to request and display status of upcoming packs'''
        if message.lower() == 'pack status':
            print('Processing pack status with message', message)
            
            # Get FFG website and use regex to get the release schedule as JSON
            packStatusPage = urllib.request.urlopen(self.urlRequest).read().decode('utf-8')
            statusDataPattern = re.compile("upcoming_data = (\[.*\]);")
            result = statusDataPattern.search(packStatusPage)
            self.releaseData = json.loads(result.group(1))
            
            # Search through upcoming release JSON for GoT items then add to then queue response
            response = ""
            for release in self.releaseData:
                if release['root_collection'] == 'A Game of Thrones: The Card Game Second Edition':
                    response += release['product'] + '  -  ' + release['name'] + '\n'
                    
            slackBot.queueResponse(self.slackBot, response)       
            return True
                    
                    
    def processHelp(self, message):
        if message.lower() == 'help':
            print('Processing help with message', message)
            slackBot.queueResponse(self.slackBot, self.helpMessage)
            
            return True
        
    def processPackList(self, message):
        ''' Method to return all cards in a pack'''
        # Split message
        deconstMessage = message.split(':')
        if len(deconstMessage) < 2:
            return False
        
        command = deconstMessage[0]
        pack = deconstMessage[1]
        
        # Check for pack command and check pack is given
        if command.lower() == 'pack' and pack != None:
            # Get all cards in given pack
            packCards = []
            for card in self.cardsList:
                if pack.lower() == card["pack_code"].lower():
                    packCards.append(card)
            # Build the response from cards list
            response = pack + " - " + packCards[0]['pack_name'] + ":"
            packResponse = self.buildPackResponse(packCards)
            # Queue response for sending
            slackBot.queueResponse(self.slackBot, response, packResponse)
            return True
        
        else: return False

    def buildCardResponse(self, card):
        ''' Method to build response from an individual card, extracting then
            formatting appropriate data '''
        
        cardType = card['type_code']
        cardPretext = ''
        
        if card['is_unique']:
            cardPretext = ":_gotunique: "
        # Start with unique emoju, then add card name as URL link to it's image 
        #followed by the faction
        cardPretext += "*<" + "https://thronesdb.com" + (card['imagesrc'] if 'imagesrc' in card else "/" ) + "|" + card['name'].upper() + ">* \n:_got" +card['faction_code']+ ': ' + card['faction_name'] + ". "
        
        # Add if card is loyal 
        if card['is_loyal']:
            cardPretext += "Loyal. "
            
        cardPretext += "*" + card['type_name'] + "*. "
        
        # Add appropriate stats based on card type
        if cardType in ['character', 'attachment', 'event', 'location']:
            if 'cost' in card:
                cardPretext += "Cost: " + str(card['cost']) + ". "
            else:
                cardPretext += "Cost: " + "_*X*_. "
                
            if cardType == 'character':
                cardPretext += "STR: " + str(card['strength']) + ". "
                if card['is_military']:
                    cardPretext += " :_gotmil: "
                if card['is_intrigue']:
                    cardPretext += " :_gotint: "
                if card['is_power']:
                    cardPretext += " :_gotpow: "
            
        elif cardType == 'plot':
            cardPretext += "Income: " + str(card['income']) + ". Initiative: " + str(card['initiative']) + ". Claim: " + str(card['claim']) + ". Reserve: " + str(card['reserve'])
            
        if cardType in ['plot','character','attachment','location']:
            cardPretext += "\n _*" + card['traits'] + "*_"
            
            
        cardText = self.formatText(card['text'])
        cardColour = self.colourMap[card['faction_code']]
        
        # Construct attachment with the constructed text and faction specific colour
        attachment = {"mrkdwn_in" : ["pretext", "text", "fields"], 
                      "pretext" : cardPretext, "text" : cardText, "color" : cardColour}
         
        return [attachment]
    
    def buildPackResponse(self, packCards):
        
        
        attachmentMap = self.colourMap.copy()
        for house in attachmentMap.keys():
            attachmentMap[house] = {"mrkdwn_in" : ["pretext", "text", "fields"], 
                      "color" : self.colourMap[house], "fields" : []}
            
        for card in packCards:
            # Build card title - Unique + name
            cardTitle = ""
            if card['is_unique']:
                cardTitle += ":_gotunique: "
            cardTitle += card['name']
            # Build card value - Short representation
            cardValue = ":_got" + card['faction_code'] + ": " + card['type_name']
            # Set card representation fields
            cardRep = {"title" : cardTitle,
                       "value" : cardValue,
                       "short" : True}
            # Add card representation to faction attachment
            attachmentMap[card['faction_code']]["fields"].append(cardRep)
        
        # Add all faction attachments to list
        attachments = []
        for house in attachmentMap.keys():
            attachments.append(attachmentMap[house])
            
        return attachments
        
        
         
    def formatText(self , htmlText):
        '''Format text, converting HTML tags to markdown'''
        text = str(htmlText)
        text = text.replace('<b>', '*')
        text = text.replace('</b>', '*')
        text = text.replace('<i>', ' _*')
        text = text.replace('</i>', '*_ ')
        text = text.replace('<abbr>', '_')
        text = text.replace('</abbr>', '_')
        text = text.replace('[intrigue]', ':_gotint_text:')
        text = text.replace('[military]', ':_gotmil_text:')
        text = text.replace('[power]', ':_gotpow_text:')
        
        for house in self.colourMap.keys():
            text = text.replace('[' + str(house) + ']', ':_got' + str(house) + ':')
        
        return text
    
    def buildColourMap(self):
        ''' Construct a map of factions as used by the ThronesDB API
             and their specific colours'''
        self.colourMap = {'lannister' : '#b30000',
                          'stark' : '#a6a6a6',
                          'baratheon' : '#e6b800',
                          'tyrell' : '#009900',
                          'thenightswatch' : '#404040',
                          'greyjoy' : '#006699',
                          'targaryen' : '#000000',
                          'martell' : '#ff9900',
                          'neutral' : '#664400'}
                          

token = os.environ.get("token")
bot = slackBot(token)
bot.start()
