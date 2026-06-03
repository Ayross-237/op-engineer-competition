from src.business.create_orders import main
from src.shared.dates import next_week
from datetime import date, timedelta


if __name__ == "__main__":
    main(next_week(today=(date.today() - timedelta(days=40)))) 