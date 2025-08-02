// Configure environment variables
const config = require("./config.json")

/*------ MODIFY THE LOG METHOD -------------*/
const log = console.log.bind(console)
console.log = (...message) => {
  let force = false;
  if (typeof message[message.length-1] === "boolean") {
    if (message[message.length-1] === true) {
      force = true;
      message = message.slice(0, message.length-1);
    }
  }
  if (config.VERBOSITY === "debug" || force === true) {
    log(...message)
  }
}
console.log("Trading mode:", config.MODE, true)

// Set up the server connection with Pocket Option
const socketio = require("socket.io-client")
const server = socketio.io(
  config.MODE == "demo"
    ? config.DEMO_SERVER
    : config.LIVE_SERVER,
  {
    extraHeaders: {
      origin: config.ORIGIN,
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
  "updateClosedDeals", "updateOpenedDeals", "successprice-alert/update",
  "successupdatePending", "successopenPendingOrder", "successprice-alert/load",
  "successpending/created", "updateAssets"
];
let isAuthenticated = false;
for (let index = 0; index <= inboundEvents.length - 1; index++) {
  server.on(inboundEvents[index], (message) => {
    console.log("Received server event:", inboundEvents[index], message, true);
    const reservedEventNames = ["connect", "disconnect", "connect_error"]
    if (!reservedEventNames.includes(inboundEvents[index])) {
      if (client && client.connected) {
        client.emit(inboundEvents[index], message);
      }

      if (inboundEvents[index] == "successauth") {
        isAuthenticated = true;
        setInterval(() => {
          server.emit("ps");
        }, 60000)
      }
    } else if (inboundEvents[index] === "connect") {
      // Meaning that we have been prevously disconnected, now a new connection has been made.
      if (isAuthenticated) {
        client.emit("connected", {id: server.id});
      }
    } else if (inboundEvents[index] == "disconnect") {
      server.connect();
    } else if (inboundEvents[index] == "connect_error") {
      client.emit("connection_error", message);
      server.connect(); 
    }
  });
}


/*----------- CLIENT EVENTS ----------------*/
const outboundEvents = [
  "connect", "disconnect", "favorite/change",
  "changeSymbol", "auth", "loadHistoryPeriod",
  "openOrder", "cancelOrder", "price-alert/add",
  "price-alert/remove", "price-alert/load",
  "openPendingOrder", "cancelPendingOrder"
]
let client = socketio.io("http://localhost:5000");
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

