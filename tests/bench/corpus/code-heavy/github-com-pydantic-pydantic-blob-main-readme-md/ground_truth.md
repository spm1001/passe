Data validation using Python type hints.

Fast and extensible, Pydantic plays nicely with your linters/IDE/brain. Define how data should be in pure, canonical Python 3.9+; validate it with Pydantic.

We've launched Pydantic Logfire to help you monitor your applications.
[Learn more](https://pydantic.dev/logfire/?utm_source=pydantic_validation)

Pydantic V2 is a ground-up rewrite that offers many new features, performance improvements, and some breaking changes compared to Pydantic V1.

If you're using Pydantic V1 you may want to look at the
[pydantic V1.10 Documentation](https://docs.pydantic.dev/) or,
[ 1.10.X-fixes git branch](https://github.com/pydantic/pydantic/tree/1.10.X-fixes). Pydantic V2 also ships with the latest version of Pydantic V1 built in so that you can incrementally upgrade your code base and projects:

`from pydantic import v1 as pydantic_v1`

.See [documentation](https://docs.pydantic.dev/) for more details.

Install using `pip install -U pydantic`

or `conda install pydantic -c conda-forge`

.
For more installation options to make Pydantic even faster,
see the [Install](https://docs.pydantic.dev/install/) section in the documentation.

```
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
class User(BaseModel):
id: int
name: str = 'John Doe'
signup_ts: Optional[datetime] = None
friends: list[int] = []
external_data = {'id': '123', 'signup_ts': '2017-06-01 12:22', 'friends': [1, '2', b'3']}
user = User(**external_data)
print(user)
#> User id=123 name='John Doe' signup_ts=datetime.datetime(2017, 6, 1, 12, 22) friends=[1, 2, 3]
print(user.id)
#> 123
```

For guidance on setting up a development environment and how to make a
contribution to Pydantic, see
[Contributing to Pydantic](https://docs.pydantic.dev/contributing/).

See our [security policy](https://github.com/pydantic/pydantic/security/policy).