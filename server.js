// Configure environment variables
import { config } from "dotenv";
import { WebSocket } from "ws";
config();

// Set up the server connection with Pocket Option
import { io } from "socket.io-client";
const server = io(
  process.env.MODE == "demo"
    ? process.env.DEMO_SERVER
    : process.env.LIVE_SERVER,
  {
    extraHeaders: {
      Origin: process.env.ORIGIN,
    },
    transports: ["websocket"],
  }
);

// Modify the on event to parse the incoming data
let client = null;
const on = server.on.bind(server);
server.on = (event, callback) => {
  on(event, (...args) => {
    if (Buffer.isBuffer(args[0])) {
      const smsg = args[0].toString("utf-8");
      try {
        args[0] = JSON.parse(smsg);
      } catch (error) {
        helpers.logger.error(error);
        args[0] = smsg;
      }
    }
    callback(...args);
  });
};

// Required server incoming events
const inboundEvents = [
  "connect", "disconnect", "successauth",
  "updateStream", "updateHistoryNew", "loadHistoryPeriod",
  "successupdateBalance", "closeOrder", "openOrder",
  "successcloseOrder", "successopenOrder", "failopenOrder",
  "updateHistory", "connect_error", "reconnect_error",
  "reconnect_failed", "updateBalance", "price-alert/load", "favorite/load",
  "updateClosedDeals", "updateOpenedDeals"
], outboundEvents = [
  "changeSymbol", "auth", "loadHistoryPeriod",
  "openOrder", "cancelOrder", "favorite/change",
  "price-alert/add", "price-alert/remove"
]

for (let index = 0; index <= inboundEvents.length - 1; index++) {
  server.on(inboundEvents[index], (message) => {
    console.log(inboundEvents[index], message, inboundEvents[index] === "connect");
    if (inboundEvents[index] === "connect") {
      const auth_data = {isDemo: process.env.MODE == "demo" ? 1 : 0,
          session: process.env.MODE == "demo" ? process.env.DEMO_AUTH : process.env.LIVE_AUTH,
          platform: Number(process.env.PLATFORM),
          uid: Number(process.env.AUTH_UID)};
        server.emit("auth", auth_data); 
    } if (inboundEvents[index] === "successauth") {
    }
  });
}

