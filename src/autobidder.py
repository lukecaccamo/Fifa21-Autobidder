import csv
from datetime import datetime
from decimal import Decimal
from time import sleep

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import Chrome, ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support import ui
from selenium.webdriver.support.wait import WebDriverWait
from datafile_manager import get_player_list

import helpers
from helpers import *


class Autobidder:
    def __init__(self, driver, queue):
        self.driver = driver
        self.queue = queue
        self.playerlist = []
        self.helper = Helper(self.driver, self.queue)

    def initializeBot(self):
        # Only on first initializatin of bot object, clear old variables etc
        self.helper.clearOldUserData()
        self.helper.setStartingCoins()
        sleep(3)
        self.start()

    # Test function called when dev mode enabled
    def test(self):
        self.checkTransferlist()
                    
    def start(self):
        log_event(self.queue, "Autobidder started")

        # Clear market logs from previous run
        self.helper.clearOldMarketLogs()

        # Get player list
        self.playerlist = get_player_list()
        bidsallowed, bidstomake_eachplayer = self.helper.getWatchlistTransferlistSize()

        self.helper.user_num_target_players = len(self.playerlist)
        self.helper.user_num_bids_each_target = bidstomake_eachplayer
        self.helper.update_autobidder_logs()

        continue_running = True
        for player in self.playerlist:
            total_bids_made = 0
            fullname = player[0]
            cardname = player[1]
            cardoverall = player[2]
            futbinprice = int(player[9])
            marketprice = int(player[11])
            buy_percent = float(player[12])
            buy_price_override = int(player[13])

            conserve_bids, sleep_time, botspeed, bidexpiration_ceiling, buyceiling, sellceiling = self.helper.getUserConfig()

            # Insert player into search box
            status = self.helper.go_to_tranfer_market_and_input_parameters(cardname, fullname, cardoverall)
            if (status == "error"):
                continue_running = False
                break

            # Get player's known value - either from FUTBIN, or from override
            known_value = futbinprice
            max_price_to_pay = 0
            log_event(self.queue, str(player[1]) + " FUTBIN price: " + str(futbinprice))

            if buy_price_override > 0:
                max_price_to_pay = buy_price_override
                log_event(self.queue, 'Overriding max buy price with: ' + str(buy_price_override))
            else:
                max_price_to_pay = int(round(buyceiling * known_value, -2))
                log_event(self.queue, str(player[1]) + " stop price = buy ceiling (" + str(buyceiling) + ") * (" + str(known_value) + ") = " + str(max_price_to_pay))

            # Modulate bid params to capture all players on market
            min_bid = 0
            # max_bid = int(round(max_price_to_pay * 0.75, -2))
            max_bid = max_price_to_pay

            for x in range(4):
                min_bid = int(round((max_bid * .8), -2))
                if (x == 3):
                    log_event(self.queue, "BidRound FINAL | MIN: " + str(min_bid) + " MAX: " + str(max_bid))
                    min_bid = 0
                    total_bids_made = self.helper.search_market_gather_players(cardname, max_price_to_pay, bidstomake_eachplayer, total_bids_made, "None", min_bid, max_bid)
                else:
                    log_event(self.queue, "BidRound " + str(x) + " | MIN: " + str(min_bid) + " MAX: " + str(max_bid))
                    total_bids_made = self.helper.search_market_gather_players(cardname, max_price_to_pay, bidstomake_eachplayer, total_bids_made, "None", min_bid, max_bid)
                    self.helper.sleep_approx(1)
                    max_bid = min_bid
            sleep(2)

        if (continue_running):
            # Parse market data to find actual sell price 
            log_event(self.queue, "Parsing market data to find most accurate sell prices...")
            self.helper.get_lowestbin_from_searchdata()

            log_event(self.queue, "Going to watchlist. Time for war")
            # self.helper.go_to_watchlist()
            self.manageWatchlist()
        else:
            log_event(self.queue, "Error, bot stopped!")


    def manageWatchlist(self):
        self.helper.go_to_watchlist()
        continue_running = True
        status = 1
        while (status == 1):
            # 1. Make sure we are on watchlist, else break (for debugging)
            page = self.driver.find_element_by_xpath("/html/body/main/section/section/div[1]/h1").text
            if (page.lower() == "transfer targets"):
                # 2. Ensure active bids exist
                # self.helper.update_autobidder_logs()
                num_activebids = self.helper.get_num_activebids()
                if (num_activebids != 0):
                    # Evaluate 5 cards closest to expiration, returns "processing" if exception
                    active_bids = self.helper.getAllPlayerInfoWatchlist()
                    # If any players are processing, bot will not bid
                    if (active_bids != "processing"):
                        firstplayer = active_bids[0]
                        firstplayer_timeremaining = firstplayer[7]
                        # Triple check that first player is not Processing (else will throw exception, redundant but necessary)
                        if (0 < firstplayer_timeremaining):
                            # If method reaches here, everything should be good to go...
                            # Iterate over cards on watchlist
                            for card in active_bids:
                                bidStatus = card[1]
                                if "outbid" in bidStatus:
                                    playername = card[3]
                                    playernumber = card[0]
                                    curbid = card[5]
                                    timeremainingseconds = card[7]
                                    timeremainingmins = timeremainingseconds/60
                                    id = card[8]
                                    sellprice = self.helper.getPlayerSellPrice(id)
                                    stopPrice = self.helper.getPlayerPriceCeiling(id)
                                    # Ensure user has enough coins to bid
                                    if (self.helper.user_num_coins >= curbid+100):
                                        # Stop price is 0 if player isn't on playerlist
                                        if (stopPrice != 0):
                                            if (curbid < 1000):
                                                curbidprice_afterbidding = curbid+50
                                            else:
                                                curbidprice_afterbidding = curbid+100
                                                
                                            if (curbidprice_afterbidding < stopPrice):
                                                result = self.helper.makebid_individualplayerWatchlist(playernumber, curbid)
                                                if result == "Failure":
                                                    log_event(self.queue, "Error outbidding " + str(playername) + ". Refreshing page")
                                                    self.helper.refreshPageAndGoToWatchlist()
                                                if result == "Success":
                                                    if (curbid <= 950):
                                                        bidlog = curbid + 50
                                                    else:
                                                        bidlog  = curbid + 100
                                                    log_event(self.queue, "Outbid " + str(playername) + " | CurBid: " + str(bidlog) + " | Stop: " + str(stopPrice) + " | Est. Prof: " + str(sellprice - curbid))
                                    else:
                                        log_event(self.queue, "You don't have enough coins to continue bidding")
                                        status = 0
                else:
                    status = 0
            else: 
                log_event(self.queue, "Unexpected page, stopping bot")
                continue_running = False
                status = 0

        if continue_running:
            log_event(self.queue, "No more active bids")
            log_event(self.queue, "Sending them to TL")
            self.finishWatchlist()
        else:
            log_event(self.queue, "Error, bot stopped!")

    # Send won players to transfer list
    def finishWatchlist(self):
        self.helper.go_to_watchlist()
        sleep(2)
        self.helper.send_won_players_to_transferlist()
        log_event(self.queue, "Now listing players")
        self.checkTransferlist()

    # List and relist won players
    def checkTransferlist(self):    
        self.helper.go_to_transferlist()
        sleep(5)
        log_event(self.queue, "Went to transfer list")

        # Lock player prices into global dict, also store it locally here as p_ids_and_prices
        transferlist_summary = self.helper.getTransferListSummary()
        p_ids_and_prices = transferlist_summary[0]

        # Proceed to ensure transferlist is fully handled in While loop
        status = True
        while status:
            num_p_sold, num_p_expired, num_p_unlisted, num_p_listed = self.helper.getTransferListSummaryWithoutPrices()

            # Check if job is done, else get to work relisting / listing
            if ((num_p_sold == 0) and (num_p_expired == 0) and (num_p_unlisted == 0)):
                status = False
            else:
                log_event(self.queue, "Status is not false")
                if (num_p_sold > 0):
                    log_event(self.queue, "cleared sold ")
                    self.helper.clearSold()

                self.helper.sleep_approx(3)

                if (num_p_expired > 0):
                    log_event(self.queue, "listing expired players..")
                    self.helper.relist_expired_players(p_ids_and_prices)
                
                self.helper.sleep_approx(3)
            
                if (num_p_unlisted > 0):
                    log_event(self.queue, "listing unlisted players .. ")
                    self.helper.list_unlisted_players(p_ids_and_prices)
        log_event(self.queue, "Finished checking TL!!!")

        # Sleepy time
        conserve_bids, sleep_time, botspeed, bidexpiration_ceiling, buyceiling, sellceiling = self.helper.getUserConfig()

        page = self.driver.find_element_by_xpath("/html/body/main/section/section/div[1]/h1").text
        if (page.lower() == "transfer list"):
            sleepmins = int(sleep_time)/60
            sleep_time = int(sleep_time)
            log_event(self.queue, "Sleepy time! for " + str(sleepmins) + " mins and heading back to war")
            sleep(sleep_time)

            
            log_event(self.queue, "Proceeding to restart")
            sleep(3)
            self.start()
        else:
            log_event(self.queue, "unexpected page, bot stopped")

        # CAPTCHA:
        # /html/body/div[4]/section/header/h1
        # that is header of msg ^^
        # OK bnutton: /html/body/div[4]/section/div/div/button