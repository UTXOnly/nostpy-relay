package main

import (
    "encoding/json"
    "log"
    "net/http"
    "os"

    "github.com/gorilla/websocket"
    "gopkg.in/DataDog/dd-trace-go.v1/ddtrace/tracer"
)

var (
    upgrader = websocket.Upgrader{}
)

type eventDict map[string]interface{}

func handleWebSocketConnection(w http.ResponseWriter, r *http.Request) {
    headers := r.Header
    referer := headers.Get("Referer")
    origin := headers.Get("Origin")
    log.Printf("New WebSocket connection established from URL: %s\n", referer)
    conn, err := upgrader.Upgrade(w, r, nil)
    if err != nil {
        log.Println(err)
        return
    }
    defer conn.Close()
    for {
        messageType, message, err := conn.ReadMessage()
        if err != nil {
            log.Println(err)
            return
        }
        switch messageType {
        case websocket.TextMessage:
            var messageList []interface{}
            err = json.Unmarshal(message, &messageList)
            if err != nil {
                log.Println(err)
                return
            }
            log.Printf("Received message: %#v \n", messageList)
            lenMessage := len(messageList)
            log.Printf("Received message length: %d\n", lenMessage)

            actions := map[string]func() error{
                "EVENT": func() error {
                    return sendEventToHandler(messageList[1].(eventDict))
                },
                "REQ": func() error {
                    return sendSubscriptionToHandler(messageList[1].(map[string]interface{}), messageList[2].(string), origin, conn)
                },
                "CLOSE": func() error {
                    log.Printf("Notice closing %s\n", messageList[1])
                    return nil
                },
            }

            action := actions[messageList[0].(string)]
            if action != nil {
                err = action()
                if err != nil {
                    log.Println(err)
                    return
                }
            } else {
                log.Printf("Unsupported message format: %#v\n", messageList)
            }
        }
    }
}

func sendEventToHandler(eventDict eventDict) error {
    url := "http://event_handler/new_event"
    body, _ := json.Marshal(eventDict)

    req, err := http.NewRequest("POST", url, bytes.NewReader(body))
    if err != nil {
        log.Println(err)
        return err
    }
    req.Header.Add("Content-Type", "application/json")

    resp, err := httpClient.Do(req)
    if err != nil {
        log.Println(err)
        return err
    }
    defer resp.Body.Close()
    var responseMap map[string]interface{}
    err = json.NewDecoder(resp.Body).Decode(&responseMap)
    if err != nil {
        log.Println(err)
        return err
    }
    log.Printf("Received response from Event Handler %#v\n", responseMap)
    return nil
}

func sendSubscriptionToHandler(eventDict map[string]interface{}, subscriptionID string, origin string, conn *websocket.Conn) error {
    url := "http://query_service/subscription"
    payload := map[string]interface{}{
        "event_dict":      eventDict,
        "subscription_id": subscriptionID,
        "origin":          origin,
    }
    body, _ := json.Marshal(payload)

    req, err := http.NewRequest("POST", url, bytes.NewReader(body))
    if err != nil {
        log.Println(err)
        return err
    }
    req.Header.Add("Content-Type", "application/json")

    resp, err := httpClient.Do(req)
    if err != nil {
        log.Println(err)
        return err
    }
    defer resp.Body.Close()
    var responseMap map[string]interface{}
    err = json.NewDecoder(resp.Body).Decode(&responseMap)
    if err != nil {
        log.Println(err)
        return err
    }

    eventType := responseMap["event"].(string)
    subscriptionID = responseMap["subscription_id"].(string)
    results := responseMap["results_json"].([]interface{})
    log.Printf("Response received as: %#v\n", responseMap)

    EOSE := []interface{}{"EOSE", subscriptionID}
    if eventType == "EOSE" {
        conn.WriteJSON(EOSE)
    } else {
        for _, eventItem := range results {
            clientResponse := []interface{}{eventType, subscriptionID, eventItem}
            conn.WriteJSON(clientResponse)
        }
        conn.WriteJSON(EOSE)
    }
    log.Printf("Sending response data: %#v\n", responseMap)
    return nil
}

func main() {
    tracer.Start(tracer.WithAgentAddr("172.28.0.5:8126"))
    defer tracer.Stop()

    logger := log.New(os.Stdout, "", log.LstdFlags|log.LUTC)
    http.HandleFunc("/", handleWebSocketConnection)
    err := http.ListenAndServe(":8008", nil)
    if err != nil {
        logger.Printf("Error starting server: %s\n", err)
    }
}
