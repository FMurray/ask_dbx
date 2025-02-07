from rich import print

from ask_dbx.agents.main import main, tech_lead as tl


def hello() -> None:
    print("Hello from ask-dbx!")
    main()


def tech_lead() -> None:
    tl()
