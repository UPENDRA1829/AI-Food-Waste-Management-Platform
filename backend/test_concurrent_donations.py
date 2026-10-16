
import asyncio
import os
import httpx

BASE_URL = "http://127.0.0.1:8000"
API_KEY = os.getenv("BUSINESS_1_API_KEY")

INVENTORY_ID = 31
NGO_ID = 1
DONATION_QUANTITY = 7


async def main():
    if not API_KEY:
        print("API key not configured.")
        print("We will configure it in the next step.")
        return

    headers = {"X-API-Key": API_KEY}

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=headers,
        timeout=30.0
    ) as client:

        response = await client.get("/inventory")

        if response.status_code != 200:
            print("Could not read inventory:", response.text)
            return

        items = response.json()
        item = next(
            (x for x in items
             if x["inventory_id"] == INVENTORY_ID),
            None
        )

        if item is None:
            print("Test inventory item not found.")
            return

        print("Starting stock:", item["quantity"], item["unit"])

        if float(item["quantity"]) != 10:
            print("STOP: Stock is not 10. No donations sent.")
            return

        async def request_donation():
            return await client.post(
                "/donations",
                params={
                    "inventory_id": INVENTORY_ID,
                    "ngo_id": NGO_ID,
                    "quantity": DONATION_QUANTITY,
                    "pickup_notes": "Concurrency test"
                }
            )

        print("Sending two requests simultaneously...")

        results = await asyncio.gather(
            request_donation(),
            request_donation(),
            return_exceptions=True
        )

        for number, result in enumerate(results, start=1):
            print(f"\nRequest {number}:")
            if isinstance(result, Exception):
                print("Error:", repr(result))
            else:
                print("Status:", result.status_code)
                print("Response:", result.text)

        final_response = await client.get("/inventory")

        if final_response.status_code == 200:
            final_items = final_response.json()
            final_item = next(
                (x for x in final_items
                 if x["inventory_id"] == INVENTORY_ID),
                None
            )
            if final_item:
                print(
                    "\nFinal stock:",
                    final_item["quantity"],
                    final_item["unit"]
                )


if __name__ == "__main__":
    asyncio.run(main())
