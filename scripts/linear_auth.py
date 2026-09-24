"""Convenience command for Linear OAuth."""

import asyncio

from scripts.partner_auth import authorize


if __name__ == "__main__":
    asyncio.run(authorize("linear"))
