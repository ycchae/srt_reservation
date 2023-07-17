""" Quickstart script for InstaPy usage """

# imports
import argparse

from srt_reservation.SRThunter import SRThunter


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='')

    parser.add_argument("--user", help="Username", type=str, metavar="1234567890")
    parser.add_argument("--psw", help="Password", type=str, metavar="abc1234")
    parser.add_argument("--dpt", help="Departure Station", type=str, metavar="동탄")
    parser.add_argument("--arr", help="Arrival Station", type=str, metavar="동대구")
    parser.add_argument("--dt", help="Departure Date", type=str, metavar="20220118")
    parser.add_argument("--tm", help="Departure Time", type=str, metavar="08, 10, 12, ...", default="00")
    parser.add_argument("--num", help="num of trains to check", type=int, metavar="2", default=2)
    parser.add_argument("--adult", help="num of adults", type=int, metavar="1", default=1)
    parser.add_argument("--kid", help="num of kids", type=int, metavar="2", default=0)
    parser.add_argument("--elder", help="num of elders", type=int, metavar="2", default=0)

    parser.add_argument("--exact_times", help="Exact Times", type=str, metavar="", default="")
    parser.add_argument("--slack", help="token_info channel_info", type=str, metavar="my_token.txt my_channel.txt", default="")
    parser.add_argument("--checkout", help="checkout_info", type=str, metavar="my_card.txt", default=True)
    parser.add_argument("--reserve", help="Reserve or not", type=bool, metavar="false", default=False)
    parser.add_argument("--greedy", help="Greedy or not", type=bool, metavar="false", default=False)

    args = parser.parse_args()
    
    SRThunter(args).run()