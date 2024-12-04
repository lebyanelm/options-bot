// Configure environment variables
import { config } from "dotenv";
config();
console.log(process.env.MODE)

// Set up the server connection with Pocket Option
import { io } from "socket.io-client";
const server = io(
  process.env.MODE == "demo"
    ? process.env.DEMO_SERVER
    : process.env.LIVE_SERVER,
  {
    extraHeaders: {
      origin: process.env.ORIGIN,
    },
    transports: ["websocket"],
  }
);

/*----------- MODIFY SERVER EVENTS ----------------*/
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

/*----------- SERVER EVENTS ----------------*/
const inboundEvents = [
  "connect", "disconnect", "successauth",
  "updateStream", "updateHistoryNew", "loadHistoryPeriod",
  "successupdateBalance", "closeOrder", "openOrder",
  "successcloseOrder", "successopenOrder", "failopenOrder",
  "updateHistory", "connect_error", "reconnect_error",
  "reconnect_failed", "updateBalance", "price-alert/load", "favorite/load",
  "updateClosedDeals", "updateOpenedDeals"
];
let isAuthenticated = false;
for (let index = 0; index <= inboundEvents.length - 1; index++) {
  server.on(inboundEvents[index], (message) => {
    console.log("Received server event:", inboundEvents[index], message);
    if (inboundEvents[index] !== "connect" && inboundEvents[index] !== "disconnect") {
      if (client && client.connected) {
        client.emit(inboundEvents[index], message);
      }

      if (inboundEvents[index] == "successauth") {
        isAuthenticated = true;
      }
    } else if (inboundEvents[index] === "connect") {
      // Meaning that we have been prevously disconnected, now a new connection has been made.
      if (isAuthenticated) {
        client.emit("connected", {id: server.id});
      }
    } else if (inboundEvents[index] == "disconnect") {
      server.connect();
    }
  });
}


/*----------- CLIENT EVENTS ----------------*/
const outboundEvents = [
  "connect", "disconnect", "favorite/change",
  "changeSymbol", "auth", "loadHistoryPeriod",
  "openOrder", "cancelOrder", "price-alert/add",
  "price-alert/remove"
]
let client = io("http://localhost:5000");
for (let j_index = 0; j_index <= outboundEvents.length-1; j_index++) {
  // When client sends messages most of them should be forwarded to the server.
  client.on(outboundEvents[j_index], (message) => {
    if (outboundEvents[j_index] !== "connect" && outboundEvents[j_index] !== "disconnect") {
      console.log("Received client event", outboundEvents[j_index], message);
      server.emit(outboundEvents[j_index], message);
    } else if (outboundEvents[j_index] == "connect") {
      client.emit("connected", {id: server.id});
    }
  })
}

