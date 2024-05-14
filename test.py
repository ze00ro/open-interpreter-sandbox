from uuid import uuid4

from interpreter import interpreter
import litellm

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from interpreter import OpenInterpreter

app = FastAPI()
request_state = {}


def record_by_request(
        kwargs,  # kwargs to completion
        completion_response,  # response from completion
        start_time,
        end_time  # start/end time
):
    try:
        # check if it has collected an entire stream response
        if "complete_streaming_response" in kwargs:
            # for tracking streaming cost we pass the "messages" and the output_text to litellm.completion_cost
            # completion_response = kwargs["complete_streaming_response"]
            # input_text = kwargs["messages"]
            # output_text = completion_response["choices"][0]["message"]["content"]
            # response_cost = litellm.completion_cost(
            #     model=kwargs["model"],
            #     messages=input_text,
            #     completion=output_text
            # )
            total_tokens = kwargs.get('complete_streaming_response', {}).get('usage', {}).get('total_tokens', 0)
            if total_tokens > 0:
                request_id = kwargs.get('litellm_params', {}).get('metadata', {}).get('request_id', {})
                if request_id:
                    print("streaming response_cost", total_tokens)
                    request_state[request_id] += total_tokens
                    print("after plus" + str(request_state))
        else:
            # for non-streaming responses
            # we pass the completion_response obj
            if not kwargs["stream"]:
                response_cost = litellm.completion_cost(completion_response=completion_response)
                print("regular response_cost", response_cost)
    except:
        pass


@app.get("/chat")
def chat_endpoint(message: str):
    litellm.success_callback = [record_by_request]

    request_id = str(uuid4())  # 创建请求的唯一标识符
    request_state[request_id] = 0  # 初始化 token 计数
    print(f'request_id is {request_id}')

    oi = OpenInterpreter()
    oi.offline = False
    oi.llm.metadata = {'request_id': request_id}
    oi.llm.api_base = 'https://gptbalance.jxjia.net/v1'
    oi.llm.model = 'gpt-4-1106-preview'
    oi.llm.api_key = "fake_key"
    oi.llm.context_window = 100000
    oi.llm.max_tokens = 4000
    oi.auto_run = True

    def event_stream():
        print("before stream event")
        for result in oi.chat(message, stream=True):
            yield f"data: {result}\n\n"
        print("after yield")
        final_cost = request_state.get(request_id, 0)
        print('final cost is:' + str(final_cost))
        del request_state[request_id]  # 清理状态

    return StreamingResponse(event_stream(), media_type="text/event-stream")
