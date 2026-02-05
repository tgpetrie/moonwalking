# Instructions for running the Sentiment Popup

The sentiment popup requires a backend service to be running. I have prepared a script to make this easy for you.

## 1. Run the backend

I have modified the `diagnose_and_fix.sh` script to install the required dependencies and start the sentiment API backend.

To run the backend, execute the following command in your terminal:

```bash
./diagnose_and_fix.sh
```

This will:
1. Install the necessary Python packages.
2. Start the sentiment API server on `http://localhost:8001`.

## 2. Open the sentiment popup

Once the backend is running, open the `sentiment-popup-production.html` file in your web browser. The popup should now be able to connect to the backend and display the sentiment data.

If the backend is not running, the popup will show mock data after a few seconds.
