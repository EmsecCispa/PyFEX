EasyHTTPRequest: Streamlined HTTP Interactions in Python
========================================================

**EasyHTTPRequest** is a Python library that elegantly combines simplicity and functionality in the domain of HTTP libraries. Designed to handle HTTP/1.1 requests with finesse, it eliminates the need for manual manipulation of query strings or intricate form-encoding of `PUT` and `POST` data, thanks to its intuitive `json` method that aligns with contemporary standards.

Effortless Interaction with HTTP/1.1
------------------------------------

Experience the power and simplicity of **EasyHTTPRequest** with the following concise and expressive code snippet:

```    
  import easyhttprequest
  r = easyhttprequest.get('https://httpbin.org/basic-auth/user/pass', auth=('user', 'pass'))
  print(r.status_code)
  # Output: 200
  print(r.headers['content-type'])
  # Output: 'application/json; charset=utf8'
  print(r.encoding)
  # Output: 'utf-8'
  print(r.text)
  # Output: '{"authenticated": true, ...'
  print(r.json())
  # Output: {'authenticated': True, ...}
```

Installation and Compatibility
------------------------------

Embark on a seamless journey of HTTP communication by effortlessly installing **EasyHTTPRequest** from the Python Package Index (PyPI) using the following command:

```   
  $ python -m pip install easyhttprequest
```

**EasyHTTPRequest** gracefully aligns itself with the progressive evolution of Python, officially supporting versions 3.7 and beyond.

Exemplary Features and Best Practices
-------------------------------------

In its commitment to meeting contemporary demands for constructing robust and dependable HTTP-centric applications, **EasyHTTPRequest** boasts an array of features and adheres to best practices:

*   **Keep-Alive & Connection Pooling:** Optimize resource utilization through efficient connection management.
*   **International Domains and URLs:** Navigate seamlessly through intricacies of internationalized domain names and URLs.
*   **Sessions with Cookie Persistence:** Maintain state across requests with the persistence of cookies.

In essence, **EasyHTTPRequest** is not just a library; it's a conduit to an elevated realm of HTTP interaction, embodying sophistication and versatility for the discerning developer.
